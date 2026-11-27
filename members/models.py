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
    introduction = models.TextField(max_length=500, blank=True)
    languages = models.CharField(max_length=255, blank=True, help_text='Languages you can chat in, separated by commas.')
    interests = models.CharField(max_length=255, blank=True, help_text='Topics you enjoy, separated by commas.')
    # Retained for existing records but hidden from the chat-focused signup flow.
    relationship_goal = models.CharField(max_length=20, choices=GOAL_CHOICES, default='Friendship')
    
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
