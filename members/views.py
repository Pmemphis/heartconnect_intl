import json
import hashlib
import hmac
import logging
import time
from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt

from .forms import ChatMessageForm, ChatReportForm, CustomerRegistrationForm, RegistrationForm, ServiceBookingForm, ServiceMessageForm, StkPushForm
from .models import Applicant, ChatMessage, ChatReport, Conversation, CustomerProfile, MemberBlock, MpesaPayment, OnlinePayment, ProviderPayout, ServiceBooking, ServiceMessage
from .mpesa import initiate_stk_push
from .online_payments import capture_paypal_order, create_paypal_order, create_stripe_checkout

logger = logging.getLogger(__name__)


def home(request):
    return render(request, 'members/index.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('account_home')
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


def customer_register(request):
    if request.user.is_authenticated:
        return redirect('customer_dashboard' if hasattr(request.user, 'customer_profile') else 'member_dashboard')
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                account = get_user_model().objects.create_user(
                    username=form.cleaned_data['email'], email=form.cleaned_data['email'],
                    password=form.cleaned_data['password'],
                )
                customer = CustomerProfile.objects.create(
                    account=account, full_name=form.cleaned_data['full_name'],
                    country=form.cleaned_data['country'],
                )
                login(request, account, backend='django.contrib.auth.backends.ModelBackend')
                payment = OnlinePayment.objects.create(
                    customer=customer, payment_type='customer_joining', provider='stripe',
                    amount_usd=settings.CUSTOMER_JOINING_FEE_USD,
                )
            return redirect('checkout_options', payment_id=payment.pk)
    else:
        form = CustomerRegistrationForm()
    return render(request, 'members/customer_register.html', {'form': form})


@login_required
def payment(request, user_id):
    applicant = get_object_or_404(Applicant, id=user_id, account=request.user)
    if applicant.status != 'payment_pending':
        return redirect('member_dashboard')
    form = StkPushForm(request.POST or None)
    try:
        amount_kes = int(settings.PROVIDER_JOINING_FEE_KES)
    except (TypeError, ValueError):
        amount_kes = 0
    if amount_kes < 1:
        messages.error(request, 'M-Pesa joining payment is not configured yet. Please contact support.')
        return render(request, 'members/payment.html', {'form': form, 'applicant': applicant, 'amount_kes': None})
    if request.method == 'POST' and form.is_valid():
        try:
            result = initiate_stk_push(form.cleaned_data['phone_number'], f'HC{applicant.pk}', amount=amount_kes)
            checkout_id = result.get('CheckoutRequestID')
            if not checkout_id:
                logger.error('Daraja response missing CheckoutRequestID: %s', result)
                messages.error(request, 'M-Pesa could not start the payment. Please try again shortly.')
            else:
                MpesaPayment.objects.create(
                    applicant=applicant,
                    phone_number=form.cleaned_data['phone_number'],
                    amount=amount_kes,
                    merchant_request_id=result.get('MerchantRequestID', ''),
                    checkout_request_id=checkout_id,
                    result_description=result.get('CustomerMessage', 'STK push sent.'),
                )
                messages.success(request, f'Check your phone and enter your M-Pesa PIN to pay KES {amount_kes:,}.')
        except Exception:
            logger.exception('Could not initiate M-Pesa payment')
            messages.error(request, 'Payment could not be started. Please try again later.')
    return render(request, 'members/payment.html', {'form': form, 'applicant': applicant, 'amount_kes': amount_kes})


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
        if amount == payment.amount and receipt:
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
                    f"Hello {applicant.full_name}, we received your one-time M-Pesa joining payment. Your profile is now awaiting confirmation. We’ll email you when it is approved.",
                    settings.DEFAULT_FROM_EMAIL, [applicant.account.email], fail_silently=True,
                )
        else:
            payment.result_description = 'Payment amount or receipt did not match the subscription.'
    payment.save(update_fields=['status', 'receipt_number', 'result_description'])
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


@login_required
def checkout_options(request, payment_id):
    customer = get_object_or_404(CustomerProfile, account=request.user)
    payment = get_object_or_404(OnlinePayment, pk=payment_id, customer=customer, status='pending')
    return render(request, 'members/checkout_options.html', {
        'payment': payment,
        'stripe_enabled': bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET),
        'paypal_enabled': bool(settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET),
    })


@login_required
def checkout_start(request, payment_id, provider):
    if request.method != 'POST':
        return redirect('checkout_options', payment_id=payment_id)
    customer = get_object_or_404(CustomerProfile, account=request.user)
    payment = get_object_or_404(OnlinePayment, pk=payment_id, customer=customer, status='pending')
    if provider not in ('stripe', 'paypal'):
        return redirect('checkout_options', payment_id=payment.pk)
    if payment.external_id:
        if payment.provider == provider and payment.checkout_url:
            return redirect(payment.checkout_url)
        messages.error(request, 'A checkout is already open for this payment. Complete it or contact support before switching methods.')
        return redirect('checkout_options', payment_id=payment.pk)
    payment.provider = provider
    payment.save(update_fields=['provider'])
    try:
        if provider == 'stripe':
            checkout_url = create_stripe_checkout(
                payment,
                request.build_absolute_uri('/payments/stripe/return/?session_id={CHECKOUT_SESSION_ID}'),
                request.build_absolute_uri('/payments/cancelled/'),
            )
        else:
            checkout_url = create_paypal_order(
                payment,
                request.build_absolute_uri('/payments/paypal/return/'),
                request.build_absolute_uri('/payments/cancelled/'),
            )
        return redirect(checkout_url)
    except Exception:
        logger.exception('Could not start %s checkout', provider)
        messages.error(request, 'Checkout could not be started. Please check back later or contact support.')
        return redirect('checkout_options', payment_id=payment.pk)


def payment_cancelled(request):
    messages.info(request, 'Payment was not completed. You can choose a payment method and try again.')
    if request.user.is_authenticated and hasattr(request.user, 'customer_profile'):
        return redirect('customer_dashboard')
    return redirect('home')


def _confirm_online_payment(payment, external_id):
    with transaction.atomic():
        payment = OnlinePayment.objects.select_for_update().get(pk=payment.pk)
        if payment.status == 'paid':
            return payment
        payment.status = 'paid'
        payment.external_id = external_id or payment.external_id
        payment.paid_at = timezone.now()
        payment.save(update_fields=['status', 'external_id', 'paid_at'])
        if payment.payment_type == 'customer_joining':
            CustomerProfile.objects.filter(pk=payment.customer_id).update(is_paid=True)
        elif payment.booking_id:
            booking = ServiceBooking.objects.select_for_update().get(pk=payment.booking_id)
            booking.status = 'awaiting_assignment'
            booking.save(update_fields=['status'])
        return payment


@login_required
def paypal_return(request):
    customer = get_object_or_404(CustomerProfile, account=request.user)
    order_id = request.GET.get('token', '')
    payment = get_object_or_404(OnlinePayment, customer=customer, provider='paypal', external_id=order_id)
    if payment.status != 'paid':
        try:
            result = capture_paypal_order(order_id)
            captures = result.get('purchase_units', [{}])[0].get('payments', {}).get('captures', [])
            capture = next((item for item in captures if item.get('status') == 'COMPLETED'), None)
            if result.get('status') == 'COMPLETED' and capture:
                amount = capture.get('amount', {})
                if amount.get('currency_code') != 'USD' or Decimal(amount.get('value', '0')) != payment.amount_usd:
                    logger.error('PayPal capture amount mismatch for payment %s', payment.pk)
                    messages.error(request, 'We could not verify the payment. Please contact support.')
                    return redirect('customer_dashboard')
                _confirm_online_payment(payment, order_id)
                messages.success(request, 'Payment received. Your booking or membership is now active.')
            else:
                messages.info(request, 'PayPal has not confirmed this payment yet.')
        except Exception:
            logger.exception('Could not capture PayPal order %s', order_id)
            messages.error(request, 'We could not confirm your PayPal payment yet. Please check your account shortly.')
    return redirect('customer_dashboard')


@login_required
def stripe_return(request):
    customer = get_object_or_404(CustomerProfile, account=request.user)
    session_id = request.GET.get('session_id', '')
    payment = get_object_or_404(OnlinePayment, customer=customer, provider='stripe', external_id=session_id)
    if payment.status == 'paid':
        messages.success(request, 'Payment received. Your booking or membership is now active.')
    else:
        messages.info(request, 'Stripe is confirming your payment. Refresh your account in a moment.')
    return redirect('customer_dashboard')


@csrf_exempt
def stripe_webhook(request):
    if request.method != 'POST':
        return HttpResponse(status=405)
    secret = settings.STRIPE_WEBHOOK_SECRET
    signature = request.headers.get('Stripe-Signature', '')
    if not secret or not signature:
        return HttpResponse(status=400)
    values = {}
    for item in signature.split(','):
        key, _, value = item.partition('=')
        values.setdefault(key, []).append(value)
    try:
        timestamp = int(values['t'][0])
        expected = hmac.new(secret.encode(), str(timestamp).encode() + b'.' + request.body, hashlib.sha256).hexdigest()
    except (KeyError, ValueError, TypeError):
        return HttpResponse(status=400)
    if abs(time.time() - timestamp) > 300 or not any(constant_time_compare(expected, value) for value in values.get('v1', [])):
        return HttpResponse(status=400)
    try:
        event = json.loads(request.body)
        if event.get('type') not in ('checkout.session.completed', 'checkout.session.async_payment_succeeded'):
            return HttpResponse(status=200)
        session = event['data']['object']
        if session.get('payment_status') != 'paid' or session.get('currency') != 'usd':
            return HttpResponse(status=200)
        payment = OnlinePayment.objects.get(pk=int(session['metadata']['payment_id']))
        if payment.provider != 'stripe' or payment.external_id != session.get('id'):
            return HttpResponse(status=400)
        if int(payment.amount_usd * 100) != int(session.get('amount_total', 0)):
            logger.error('Stripe checkout amount mismatch for payment %s', payment.pk)
            return HttpResponse(status=400)
        _confirm_online_payment(payment, session['id'])
    except (ValueError, KeyError, TypeError, OnlinePayment.DoesNotExist):
        logger.exception('Invalid Stripe checkout webhook')
        return HttpResponse(status=400)
    return HttpResponse(status=200)


@login_required
def customer_dashboard(request):
    customer = get_object_or_404(CustomerProfile, account=request.user)
    bookings = customer.bookings.select_related('provider').order_by('-created_at')
    providers = Applicant.objects.filter(status='approved', is_paid=True).filter(Q(offers_paid_chat=True) | Q(teaches_kiswahili=True))
    return render(request, 'members/customer_dashboard.html', {
        'customer': customer, 'bookings': bookings, 'providers': providers,
        'membership_fee_usd': settings.CUSTOMER_JOINING_FEE_USD,
    })


@login_required
def book_service(request, provider_id):
    customer = get_object_or_404(CustomerProfile, account=request.user)
    if not customer.is_paid:
        messages.info(request, 'Complete the $8.50 customer joining payment before booking a service.')
        payment = customer.payments.filter(payment_type='customer_joining', status='pending').order_by('-created_at').first()
        if not payment:
            payment = OnlinePayment.objects.create(
                customer=customer, payment_type='customer_joining', provider='stripe',
                amount_usd=settings.CUSTOMER_JOINING_FEE_USD,
            )
        return redirect('checkout_options', payment_id=payment.pk)
    provider = get_object_or_404(Applicant, pk=provider_id, status='approved', is_paid=True)
    form = ServiceBookingForm(request.POST or None, provider=provider)
    if request.method == 'POST' and form.is_valid():
        service = form.cleaned_data['service_type']
        if service == 'chat':
            amount = provider.chat_rate_usd * form.cleaned_data['chat_hours']
        else:
            amount = provider.lesson_rate_usd
        booking = ServiceBooking.objects.create(
            customer=customer, provider=provider, service_type=service,
            scheduled_at=form.cleaned_data['scheduled_at'],
            chat_hours=form.cleaned_data['chat_hours'], amount_usd=amount,
            payout_usd=amount,
        )
        payment = OnlinePayment.objects.create(
            customer=customer, booking=booking, payment_type='service_booking',
            provider='stripe', amount_usd=amount,
        )
        return redirect('checkout_options', payment_id=payment.pk)
    return render(request, 'members/book_service.html', {'form': form, 'provider': provider})


@login_required
def complete_booking(request, booking_id):
    if request.method != 'POST':
        return redirect('member_dashboard')
    provider = get_object_or_404(Applicant, account=request.user)
    booking = get_object_or_404(ServiceBooking, pk=booking_id, provider=provider, status='assigned')
    booking.status = 'completed'
    booking.completed_at = timezone.now()
    booking.save(update_fields=['status', 'completed_at'])
    messages.success(request, 'Booking marked complete. Your payout remains visible in your earnings.')
    return redirect('member_dashboard')


@login_required
def service_chat(request, booking_id):
    booking = get_object_or_404(ServiceBooking.objects.select_related('customer__account', 'provider__account'), pk=booking_id)
    is_customer = booking.customer.account_id == request.user.id
    is_provider = booking.provider_id and booking.provider.account_id == request.user.id
    if not (is_customer or is_provider):
        return redirect('account_home')
    if booking.service_type != 'chat' or booking.status != 'assigned' or not booking.provider_id:
        messages.info(request, 'This paid conversation is not available yet.')
        return redirect('customer_dashboard' if is_customer else 'member_dashboard')
    start = booking.scheduled_at
    end = start + timedelta(hours=booking.chat_hours)
    session_open = start <= timezone.now() < end
    form = ServiceMessageForm(request.POST or None)
    if request.method == 'POST' and session_open and form.is_valid():
        ServiceMessage.objects.create(booking=booking, sender=request.user, body=form.cleaned_data['body'])
        return redirect('service_chat', booking_id=booking.pk)
    return render(request, 'members/service_chat.html', {
        'booking': booking,
        'messages_list': booking.messages.select_related('sender'),
        'form': form,
        'session_open': session_open,
        'session_upcoming': timezone.now() < start,
        'customer_side': is_customer,
        'other_name': booking.provider.full_name if is_customer else booking.customer.full_name,
        'session_end': end,
    })


@login_required
def member_dashboard(request):
    if hasattr(request.user, 'customer_profile'):
        return redirect('customer_dashboard')
    applicant = get_object_or_404(Applicant, account=request.user)
    if applicant.can_use_app:
        bookings = applicant.service_bookings.select_related('customer').order_by('-created_at')
        payouts = applicant.payouts.select_related('booking').order_by('-created_at')
        return render(request, 'members/dashboard.html', {'applicant': applicant, 'bookings': bookings, 'payouts': payouts})
    return render(request, 'members/status.html', {'applicant': applicant})


@login_required
def account_home(request):
    if hasattr(request.user, 'customer_profile'):
        return redirect('customer_dashboard')
    return redirect('member_dashboard')


def _active_member(request):
    applicant = get_object_or_404(Applicant, account=request.user)
    if not applicant.can_use_app:
        return None
    return applicant


@login_required
def member_directory(request):
    if hasattr(request.user, 'customer_profile'):
        return redirect('customer_dashboard')
    applicant = _active_member(request)
    if applicant is None:
        return redirect('member_dashboard')
    members = Applicant.objects.filter(status='approved', is_paid=True).exclude(pk=applicant.pk)
    members = members.exclude(blocks_received__blocker=applicant).exclude(blocks_made__blocked=applicant)
    search = request.GET.get('q', '').strip()
    if search:
        members = members.filter(
            Q(full_name__icontains=search) | Q(country__icontains=search) |
            Q(introduction__icontains=search) | Q(languages__icontains=search) |
            Q(interests__icontains=search)
        )
    return render(request, 'members/directory.html', {'applicant': applicant, 'members': members.distinct(), 'search': search})


@login_required
def start_conversation(request, member_id):
    if request.method != 'POST':
        return redirect('member_directory')
    applicant = _active_member(request)
    if applicant is None:
        return redirect('member_dashboard')
    other = get_object_or_404(Applicant, pk=member_id, status='approved', is_paid=True)
    if other.pk == applicant.pk:
        return redirect('member_directory')
    blocked = MemberBlock.objects.filter(
        Q(blocker=applicant, blocked=other) | Q(blocker=other, blocked=applicant)
    ).exists()
    if blocked:
        messages.error(request, 'This conversation is unavailable.')
        return redirect('member_directory')
    first, second = sorted((applicant, other), key=lambda member: member.pk)
    conversation, _ = Conversation.objects.get_or_create(member_one=first, member_two=second)
    return redirect('conversation_detail', conversation_id=conversation.pk)


@login_required
def inbox(request):
    applicant = _active_member(request)
    if applicant is None:
        return redirect('member_dashboard')
    conversations = Conversation.objects.filter(Q(member_one=applicant) | Q(member_two=applicant)).select_related('member_one', 'member_two')
    conversations = conversations.exclude(
        Q(member_one__blocks_made__blocked=applicant) | Q(member_two__blocks_made__blocked=applicant) |
        Q(member_one__blocks_received__blocker=applicant) | Q(member_two__blocks_received__blocker=applicant)
    ).distinct()
    items = [{'conversation': conversation, 'other': conversation.other_member(applicant)} for conversation in conversations]
    return render(request, 'members/inbox.html', {'applicant': applicant, 'conversations': items})


@login_required
def conversation_detail(request, conversation_id):
    applicant = _active_member(request)
    if applicant is None:
        return redirect('member_dashboard')
    conversation = get_object_or_404(
        Conversation.objects.select_related('member_one', 'member_two'), pk=conversation_id
    )
    if not conversation.has_member(applicant):
        return redirect('inbox')
    other = conversation.other_member(applicant)
    if not other.can_use_app:
        messages.info(request, 'This member’s account is not currently active.')
        return redirect('inbox')
    blocked = MemberBlock.objects.filter(
        Q(blocker=applicant, blocked=other) | Q(blocker=other, blocked=applicant)
    ).exists()
    if blocked:
        messages.info(request, 'This conversation is unavailable.')
        return redirect('inbox')
    form = ChatMessageForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ChatMessage.objects.create(conversation=conversation, sender=applicant, body=form.cleaned_data['body'])
        conversation.save(update_fields=['updated_at'])
        return redirect('conversation_detail', conversation_id=conversation.pk)
    return render(request, 'members/conversation.html', {
        'applicant': applicant, 'other': other, 'conversation': conversation,
        'messages_list': conversation.messages.select_related('sender'), 'form': form,
        'report_form': ChatReportForm(),
    })


@login_required
def conversation_updates(request, conversation_id):
    applicant = _active_member(request)
    if applicant is None:
        return JsonResponse({'detail': 'Active membership required.'}, status=403)
    conversation = get_object_or_404(Conversation, pk=conversation_id)
    if not conversation.has_member(applicant):
        return JsonResponse({'detail': 'Conversation unavailable.'}, status=404)
    other = conversation.other_member(applicant)
    if not other.can_use_app or MemberBlock.objects.filter(
        Q(blocker=applicant, blocked=other) | Q(blocker=other, blocked=applicant)
    ).exists():
        return JsonResponse({'detail': 'Conversation unavailable.'}, status=403)
    try:
        after = max(0, int(request.GET.get('after', '0')))
    except (TypeError, ValueError):
        after = 0
    new_messages = conversation.messages.filter(pk__gt=after).select_related('sender')[:100]
    data = [{
        'id': message.pk,
        'body': message.body,
        'created_at': message.created_at.isoformat(),
        'sent_by_you': message.sender_id == applicant.pk,
    } for message in new_messages]
    response = JsonResponse({'messages': data})
    response['Cache-Control'] = 'no-store'
    return response


@login_required
def conversation_safety(request, conversation_id):
    if request.method != 'POST':
        return redirect('inbox')
    applicant = _active_member(request)
    if applicant is None:
        return redirect('member_dashboard')
    conversation = get_object_or_404(Conversation, pk=conversation_id)
    if not conversation.has_member(applicant):
        return redirect('inbox')
    other = conversation.other_member(applicant)
    action = request.POST.get('action')
    if action == 'block':
        MemberBlock.objects.get_or_create(blocker=applicant, blocked=other)
        messages.success(request, 'Member blocked. They can no longer message you.')
    elif action == 'report':
        form = ChatReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.reporter = applicant
            report.reported = other
            report.conversation = conversation
            report.save()
            messages.success(request, 'Your report was sent to our review team.')
        else:
            messages.error(request, 'Please add a short reason before sending your report.')
    if action == 'block':
        return redirect('inbox')
    return redirect('conversation_detail', conversation_id=conversation.pk)
