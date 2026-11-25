import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt

from .forms import RegistrationForm, StkPushForm
from .models import Applicant, MpesaPayment
from .mpesa import initiate_stk_push

logger = logging.getLogger(__name__)


def home(request):
    return render(request, 'members/index.html')


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                account = get_user_model().objects.create_user(
                    username=form.cleaned_data['email'],
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password'],
                )
                applicant = form.save(commit=False)
                applicant.account = account
                applicant.save()
                login(request, account, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('payment', user_id=applicant.id)
    else:
        form = RegistrationForm()
    return render(request, 'members/register.html', {'form': form})


@login_required
def payment(request, user_id):
    applicant = get_object_or_404(Applicant, id=user_id, account=request.user)
    if applicant.status != 'payment_pending':
        return redirect('member_dashboard')
    form = StkPushForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            result = initiate_stk_push(form.cleaned_data['phone_number'], f'HC{applicant.pk}')
            checkout_id = result.get('CheckoutRequestID')
            if not checkout_id:
                logger.error('Daraja response missing CheckoutRequestID: %s', result)
                messages.error(request, 'M-Pesa could not start the payment. Please try again shortly.')
            else:
                MpesaPayment.objects.create(
                    applicant=applicant,
                    phone_number=form.cleaned_data['phone_number'],
                    merchant_request_id=result.get('MerchantRequestID', ''),
                    checkout_request_id=checkout_id,
                    result_description=result.get('CustomerMessage', 'STK push sent.'),
                )
                messages.success(request, 'Check your phone and enter your M-Pesa PIN to pay KES 130.')
        except Exception:
            logger.exception('Could not initiate M-Pesa payment')
            messages.error(request, 'Payment could not be started. Please try again later.')
    return render(request, 'members/payment.html', {'form': form, 'applicant': applicant})


@csrf_exempt
def mpesa_callback(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'POST required'}, status=405)
    try:
        body = json.loads(request.body)
        callback = body['Body']['stkCallback']
        payment = MpesaPayment.objects.get(checkout_request_id=callback['CheckoutRequestID'])
    except (ValueError, KeyError, TypeError, MpesaPayment.DoesNotExist):
        logger.warning('Invalid or unknown Daraja callback')
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

    if payment.status != 'initiated':
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Already processed'})
    payment.result_description = callback.get('ResultDesc', '')[:255]
    payment.status = 'failed'
    if callback.get('ResultCode') == 0:
        metadata = {item['Name']: item.get('Value') for item in callback.get('CallbackMetadata', {}).get('Item', [])}
        try:
            amount = int(metadata.get('Amount', 0))
            receipt = str(metadata.get('MpesaReceiptNumber', ''))
        except (TypeError, ValueError):
            amount, receipt = 0, ''
        if amount == 130 and receipt:
            payment.status = 'confirmed'
            payment.receipt_number = receipt[:32]
            applicant = payment.applicant
            applicant.is_paid = True
            applicant.status = 'awaiting_confirmation'
            applicant.mpesa_receipt = receipt[:32]
            applicant.save(update_fields=['is_paid', 'status', 'mpesa_receipt'])
            if applicant.account and applicant.account.email:
                send_mail(
                    'Payment received — awaiting confirmation',
                    f"Hello {applicant.full_name}, we received your KES 130 subscription payment. Your profile is now awaiting confirmation. We’ll email you when it is approved.",
                    settings.DEFAULT_FROM_EMAIL, [applicant.account.email], fail_silently=True,
                )
        else:
            payment.result_description = 'Payment amount or receipt did not match the subscription.'
    payment.save(update_fields=['status', 'receipt_number', 'result_description'])
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


@login_required
def member_dashboard(request):
    applicant = get_object_or_404(Applicant, account=request.user)
    if applicant.can_use_app:
        return render(request, 'members/dashboard.html', {'applicant': applicant})
    return render(request, 'members/status.html', {'applicant': applicant})
