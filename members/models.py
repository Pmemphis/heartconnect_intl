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
    pref_age = models.CharField(max_length=50, blank=True, default='')
    pref_countries = models.CharField(max_length=255, blank=True, default='')
    introduction = models.TextField(max_length=500, blank=True)
    languages = models.CharField(max_length=255, blank=True, help_text='Languages you can chat in, separated by commas.')
    interests = models.CharField(max_length=255, blank=True, help_text='Topics you enjoy, separated by commas.')
    # Retained for existing records but hidden from the chat-focused signup flow.
    relationship_goal = models.CharField(max_length=20, choices=GOAL_CHOICES, default='Friendship')
    offers_paid_chat = models.BooleanField(default=True)
    chat_rate_usd = models.DecimalField(max_digits=5, decimal_places=2, default=3.00)
    teaches_kiswahili = models.BooleanField(default=False)
    lesson_rate_usd = models.DecimalField(max_digits=5, decimal_places=2, default=15.00)
    payout_method = models.CharField(max_length=20, choices=[('mpesa', 'M-Pesa'), ('airtel', 'Airtel Money'), ('paypal', 'PayPal')], default='mpesa')
    payout_destination = models.CharField(max_length=255, blank=True, help_text='Phone number for M-Pesa/Airtel Money or PayPal email.')
    
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


class CustomerProfile(models.Model):
    account = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer_profile')
    full_name = models.CharField(max_length=255)
    country = models.CharField(max_length=100)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.full_name} ({self.country})'


class OnlinePayment(models.Model):
    PAYMENT_TYPES = [('customer_joining', 'Customer joining fee'), ('service_booking', 'Service booking')]
    PROVIDERS = [('stripe', 'Stripe'), ('paypal', 'PayPal')]
    STATUSES = [('pending', 'Pending'), ('paid', 'Paid'), ('failed', 'Failed')]

    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name='payments')
    booking = models.ForeignKey('ServiceBooking', on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    payment_type = models.CharField(max_length=30, choices=PAYMENT_TYPES)
    provider = models.CharField(max_length=20, choices=PROVIDERS)
    amount_usd = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUSES, default='pending')
    external_id = models.CharField(max_length=255, blank=True, db_index=True)
    checkout_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.get_payment_type_display()} ${self.amount_usd} — {self.status}'


class ServiceBooking(models.Model):
    SERVICES = [('chat', 'Paid conversation'), ('kiswahili', 'Kiswahili lesson')]
    STATUSES = [
        ('awaiting_payment', 'Awaiting payment'),
        ('awaiting_assignment', 'Paid, awaiting assignment'),
        ('assigned', 'Assigned'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    customer = models.ForeignKey(CustomerProfile, on_delete=models.PROTECT, related_name='bookings')
    provider = models.ForeignKey(Applicant, on_delete=models.PROTECT, null=True, blank=True, related_name='service_bookings')
    service_type = models.CharField(max_length=20, choices=SERVICES)
    scheduled_at = models.DateTimeField()
    chat_hours = models.PositiveSmallIntegerField(default=1, help_text='Used for paid chat; lessons are fixed at two hours.')
    amount_usd = models.DecimalField(max_digits=8, decimal_places=2)
    payout_usd = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=30, choices=STATUSES, default='awaiting_payment')
    meeting_url = models.URLField(blank=True, help_text='Add the Google Meet or other voice/video link after assignment.')
    notes = models.TextField(blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.get_service_type_display()} for {self.customer.full_name} — {self.status}'


class ServiceMessage(models.Model):
    booking = models.ForeignKey(ServiceBooking, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='service_messages')
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Booking {self.booking_id} message from {self.sender}'


class ProviderPayout(models.Model):
    STATUSES = [('due', 'Due'), ('paid', 'Paid')]
    booking = models.OneToOneField(ServiceBooking, on_delete=models.PROTECT, related_name='payout')
    provider = models.ForeignKey(Applicant, on_delete=models.PROTECT, related_name='payouts')
    amount_usd = models.DecimalField(max_digits=8, decimal_places=2)
    amount_kes = models.PositiveIntegerField(null=True, blank=True)
    usd_kes_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    method = models.CharField(max_length=20, choices=[('mpesa', 'M-Pesa'), ('airtel', 'Airtel Money'), ('paypal', 'PayPal')])
    destination = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUSES, default='due')
    transfer_reference = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.provider.full_name} — ${self.amount_usd} ({self.status})'


class Conversation(models.Model):
    member_one = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='conversations_as_one')
    member_two = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='conversations_as_two')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['member_one', 'member_two'], name='unique_member_conversation'),
            models.CheckConstraint(condition=~models.Q(member_one=models.F('member_two')), name='conversation_members_differ'),
        ]
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.member_one} and {self.member_two}'

    def has_member(self, applicant):
        return applicant.pk in (self.member_one_id, self.member_two_id)

    def other_member(self, applicant):
        return self.member_two if self.member_one_id == applicant.pk else self.member_one


class ChatMessage(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='sent_chat_messages')
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Message from {self.sender} at {self.created_at:%Y-%m-%d %H:%M}'


class MemberBlock(models.Model):
    blocker = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='blocks_made')
    blocked = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='blocks_received')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['blocker', 'blocked'], name='unique_member_block'),
            models.CheckConstraint(condition=~models.Q(blocker=models.F('blocked')), name='member_cannot_block_self'),
        ]


class ChatReport(models.Model):
    STATUS_CHOICES = [('open', 'Open'), ('reviewed', 'Reviewed'), ('closed', 'Closed')]
    reporter = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='chat_reports_made')
    reported = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='chat_reports_received')
    conversation = models.ForeignKey(Conversation, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    reason = models.TextField(max_length=1000)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
