from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from .models import Applicant, ChatMessage, ChatReport, Conversation, CustomerProfile, MemberBlock, MpesaPayment, OnlinePayment, ProviderPayout, ServiceBooking, ServiceMessage

@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    # This defines what columns you see in the main list
    list_display = ('thumbnail', 'full_name', 'country', 'gender', 'age', 'offers_paid_chat', 'teaches_kiswahili', 'is_paid', 'status', 'created_at')
    
    # These filters appear on the right side for quick sorting
    list_filter = ('status', 'is_paid', 'offers_paid_chat', 'teaches_kiswahili', 'gender', 'country')
    exclude = ('relationship_goal', 'has_kids', 'kids_info')
    
    # Search bar to find users by name or phone
    search_fields = ('full_name', 'whatsapp_number', 'occupation')
    
    # Making the 'is_paid' field clickable directly from the list for speed
    list_editable = ('status',)
    readonly_fields = ('is_paid', 'mpesa_receipt')

    # Function to show a small profile picture in the admin list
    def thumbnail(self, obj):
        if obj.profile_photo:
            return format_html('<img src="{}" style="width: 45px; height:45px; border-radius:50%; object-fit:cover;" />', obj.profile_photo.url)
        return "No Photo"
    
    thumbnail.short_description = 'Photo'

    def save_model(self, request, obj, form, change):
        if obj.status == 'approved' and not obj.is_paid:
            raise ValidationError('An earner must have a confirmed joining payment before approval.')
        previous_status = Applicant.objects.filter(pk=obj.pk).values_list('status', flat=True).first() if change else None
        super().save_model(request, obj, form, change)
        if obj.status == 'approved' and previous_status != 'approved' and obj.account and obj.account.email:
            send_mail(
                'Your HeartConnect account is confirmed',
                f"Hello {obj.full_name}, your earner profile has been confirmed. You can now log in and receive paid conversation or Kiswahili lesson assignments.",
                settings.DEFAULT_FROM_EMAIL, [obj.account.email], fail_silently=True,
            )


@admin.register(MpesaPayment)
class MpesaPaymentAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'amount', 'phone_number', 'receipt_number', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('applicant__full_name', 'phone_number', 'receipt_number', 'checkout_request_id')
    readonly_fields = ('applicant', 'phone_number', 'amount', 'merchant_request_id', 'checkout_request_id', 'receipt_number', 'status', 'result_description', 'created_at')

# Customize the Admin Header
admin.site.site_header = "HeartConnect International Admin"
admin.site.site_title = "HeartConnect Portal"
admin.site.index_title = "International Chat Memberships"


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'country', 'is_paid', 'created_at')
    list_filter = ('is_paid', 'country')
    search_fields = ('full_name', 'country', 'account__email')
    readonly_fields = ('account', 'created_at')


@admin.register(OnlinePayment)
class OnlinePaymentAdmin(admin.ModelAdmin):
    list_display = ('customer', 'payment_type', 'provider', 'amount_usd', 'status', 'created_at')
    list_filter = ('payment_type', 'provider', 'status', 'created_at')
    search_fields = ('customer__full_name', 'external_id')
    readonly_fields = ('customer', 'booking', 'payment_type', 'provider', 'amount_usd', 'status', 'external_id', 'checkout_url', 'created_at', 'paid_at')


@admin.register(ServiceBooking)
class ServiceBookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'service_type', 'provider', 'scheduled_at', 'amount_usd', 'status')
    list_filter = ('service_type', 'status', 'scheduled_at')
    search_fields = ('customer__full_name', 'provider__full_name')
    readonly_fields = ('customer', 'service_type', 'scheduled_at', 'chat_hours', 'amount_usd', 'payout_usd', 'assigned_at', 'completed_at', 'created_at')

    def save_model(self, request, obj, form, change):
        if obj.status == 'assigned':
            if not obj.payments.filter(status='paid').exists():
                raise ValidationError('A booking must have a confirmed customer payment before assignment.')
            if not obj.provider_id:
                raise ValidationError('Choose an earner before assigning this booking.')
            if not obj.provider.can_use_app:
                raise ValidationError('The selected earner must have an approved, paid account.')
            if obj.service_type == 'chat' and not obj.provider.offers_paid_chat:
                raise ValidationError('The selected earner does not offer paid conversation sessions.')
            if obj.service_type == 'kiswahili' and not obj.provider.teaches_kiswahili:
                raise ValidationError('The selected earner does not offer Kiswahili lessons.')
            expected_rate = obj.provider.chat_rate_usd * obj.chat_hours if obj.service_type == 'chat' else obj.provider.lesson_rate_usd
            if expected_rate != obj.amount_usd or expected_rate != obj.payout_usd:
                raise ValidationError('Booking price and earner payout must match the selected service rate.')
            payout_usd_kes_rate = None
            payout_amount_kes = None
            if obj.provider.payout_method in ('mpesa', 'airtel'):
                try:
                    payout_usd_kes_rate = Decimal(settings.PAYOUT_USD_KES_RATE)
                except (InvalidOperation, TypeError, ValueError):
                    raise ValidationError('Set PAYOUT_USD_KES_RATE before assigning a booking to an M-Pesa or Airtel earner.')
                if payout_usd_kes_rate <= 0:
                    raise ValidationError('PAYOUT_USD_KES_RATE must be greater than zero.')
                payout_amount_kes = int((obj.payout_usd * payout_usd_kes_rate).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            if not obj.provider.payout_destination:
                raise ValidationError('The selected earner must add a payout destination before assignment.')
            existing_payout = ProviderPayout.objects.filter(booking_id=obj.pk).first() if obj.pk else None
            if existing_payout and existing_payout.provider_id != obj.provider_id:
                raise ValidationError('This booking already has a payout for another earner and cannot be reassigned.')
            if not obj.assigned_at:
                obj.assigned_at = timezone.now()
        previous_status = ServiceBooking.objects.filter(pk=obj.pk).values_list('status', flat=True).first() if change else None
        super().save_model(request, obj, form, change)
        if obj.status == 'assigned' and previous_status != 'assigned' and obj.provider_id:
            ProviderPayout.objects.get_or_create(
                booking=obj,
                defaults={
                    'provider': obj.provider,
                    'amount_usd': obj.payout_usd,
                    'amount_kes': payout_amount_kes,
                    'usd_kes_rate': payout_usd_kes_rate,
                    'method': obj.provider.payout_method,
                    'destination': obj.provider.payout_destination,
                },
            )
            details = f"{obj.get_service_type_display()} scheduled for {obj.scheduled_at} (East Africa Time)."
            if obj.meeting_url:
                details += f' Meeting link: {obj.meeting_url}'
            recipients = [email for email in (obj.customer.account.email, obj.provider.account.email) if email]
            if recipients:
                send_mail(
                    'Your HeartConnect booking is assigned',
                    f'Your paid HeartConnect booking is assigned. {details}',
                    settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=True,
                )


@admin.register(ProviderPayout)
class ProviderPayoutAdmin(admin.ModelAdmin):
    list_display = ('provider', 'booking', 'amount_usd', 'amount_kes', 'method', 'destination', 'status', 'created_at', 'paid_at')
    list_filter = ('method', 'status', 'created_at')
    search_fields = ('provider__full_name', 'destination', 'transfer_reference')
    readonly_fields = ('booking', 'provider', 'amount_usd', 'amount_kes', 'usd_kes_rate', 'method', 'destination', 'created_at')

    def save_model(self, request, obj, form, change):
        if obj.status == 'paid' and not obj.transfer_reference.strip():
            raise ValidationError('Enter the M-Pesa, Airtel Money, or PayPal transfer reference before marking a payout paid.')
        if obj.status == 'paid' and not obj.paid_at:
            obj.paid_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(ServiceMessage)
class ServiceMessageAdmin(admin.ModelAdmin):
    list_display = ('booking', 'sender', 'created_at')
    search_fields = ('sender__email', 'body')
    readonly_fields = ('booking', 'sender', 'body', 'created_at')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('member_one', 'member_two', 'created_at', 'updated_at')
    search_fields = ('member_one__full_name', 'member_two__full_name')
    readonly_fields = ('member_one', 'member_two', 'created_at', 'updated_at')


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'conversation', 'created_at')
    search_fields = ('sender__full_name', 'body')
    readonly_fields = ('conversation', 'sender', 'body', 'created_at')
    date_hierarchy = 'created_at'


@admin.register(ChatReport)
class ChatReportAdmin(admin.ModelAdmin):
    list_display = ('reporter', 'reported', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    list_editable = ('status',)
    search_fields = ('reporter__full_name', 'reported__full_name', 'reason')
    readonly_fields = ('reporter', 'reported', 'conversation', 'reason', 'created_at')


@admin.register(MemberBlock)
class MemberBlockAdmin(admin.ModelAdmin):
    list_display = ('blocker', 'blocked', 'created_at')
    readonly_fields = ('blocker', 'blocked', 'created_at')
