from django.conf import settings
from django.db import models

class Applicant(models.Model):
    STATUS_CHOICES = [
        ('payment_pending', 'Payment pending'),
        ('awaiting_confirmation', 'Awaiting confirmation'),
        ('approved', 'Approved'),
        ('rejected', 'Not approved'),
    ]
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female')]
    GOAL_CHOICES = [('Marriage', 'Marriage'), ('Serious', 'Serious Relationship'), ('Friendship', 'Friendship')]
    
    # Personal Details
    full_name = models.CharField(max_length=255)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    age = models.PositiveIntegerField()
    occupation = models.CharField(max_length=255)
    whatsapp_number = models.CharField(max_length=20)
    
    # Family info
    has_kids = models.BooleanField(default=False)
    kids_info = models.TextField(blank=True, null=True)
    
    # Preferences
    pref_age = models.CharField(max_length=50)
    pref_countries = models.CharField(max_length=255)
    relationship_goal = models.CharField(max_length=20, choices=GOAL_CHOICES)
    
    profile_photo = models.ImageField(upload_to='profiles/')
    account = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='member_profile', null=True, blank=True)
    mpesa_receipt = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='payment_pending')
    is_paid = models.BooleanField(default=False)  # Kept for existing records; payment is verified by an administrator.
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name

    @property
    def can_use_app(self):
        return self.is_paid and self.status == 'approved'


class MpesaPayment(models.Model):
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='payments')
    phone_number = models.CharField(max_length=12)
    amount = models.PositiveIntegerField(default=130)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    checkout_request_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    receipt_number = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=20, default='initiated')
    result_description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.applicant.full_name} — KES {self.amount} ({self.status})'
