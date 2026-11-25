from django.contrib import admin
from django.utils.html import format_html
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import ValidationError
from .models import Applicant, MpesaPayment

@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    # This defines what columns you see in the main list
    list_display = ('thumbnail', 'full_name', 'country', 'gender', 'age', 'is_paid', 'status', 'created_at')
    
    # These filters appear on the right side for quick sorting
    list_filter = ('status', 'is_paid', 'gender', 'relationship_goal', 'country', 'has_kids')
    
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
            raise ValidationError('A member must have a confirmed KES 130 payment before approval.')
        previous_status = Applicant.objects.filter(pk=obj.pk).values_list('status', flat=True).first() if change else None
        super().save_model(request, obj, form, change)
        if obj.status == 'approved' and previous_status != 'approved' and obj.account and obj.account.email:
            send_mail(
                'Your HeartConnect account is confirmed',
                f"Hello {obj.full_name}, your profile has been confirmed. You can now log in and use HeartConnect.",
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
admin.site.index_title = "Matchmaking Management"
