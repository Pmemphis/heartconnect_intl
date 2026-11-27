import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt

from .forms import ChatMessageForm, ChatReportForm, RegistrationForm, StkPushForm
from .models import Applicant, ChatMessage, ChatReport, Conversation, MemberBlock, MpesaPayment
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
                    f"Hello {applicant.full_name}, we received your one-time KES 130 membership payment. Your profile is now awaiting confirmation. We’ll email you when it is approved.",
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


def _active_member(request):
    applicant = get_object_or_404(Applicant, account=request.user)
    if not applicant.can_use_app:
        return None
    return applicant


@login_required
def member_directory(request):
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
