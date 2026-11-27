from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from .models import Applicant
from .models import ChatMessage, ChatReport, ServiceMessage

class RegistrationForm(forms.ModelForm):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)

    class Meta:
        model = Applicant
        fields = [
            'full_name', 'country', 'city', 'gender', 'age', 'occupation',
            'whatsapp_number', 'profile_photo',
            'introduction', 'languages', 'interests', 'offers_paid_chat',
            'chat_rate_usd', 'teaches_kiswahili', 'lesson_rate_usd',
            'payout_method', 'payout_destination',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields([
            'full_name', 'email', 'password', 'country', 'city', 'gender', 'age',
            'occupation', 'whatsapp_number', 'languages', 'interests',
            'introduction', 'offers_paid_chat', 'chat_rate_usd', 'teaches_kiswahili',
            'lesson_rate_usd', 'payout_method', 'payout_destination',
            'profile_photo',
        ])
        self.fields['email'].label = 'Email address'
        self.fields['email'].help_text = 'We’ll use this for your confirmation and account updates.'
        self.fields['password'].label = 'Create a password'
        self.fields['password'].help_text = 'Use at least 8 characters.'
        self.fields['whatsapp_number'].label = 'WhatsApp number'
        self.fields['whatsapp_number'].help_text = 'Include your country code, for example +254712345678.'
        self.fields['profile_photo'].label = 'Profile photo'
        self.fields['profile_photo'].help_text = 'Choose a clear photo of yourself.'
        self.fields['introduction'].label = 'A little about you'
        self.fields['introduction'].help_text = 'Up to 500 characters. Share the kind of friendly company you enjoy.'
        self.fields['languages'].label = 'Languages'
        self.fields['interests'].label = 'Conversation topics and interests'
        self.fields['offers_paid_chat'].label = 'Offer paid conversation sessions'
        self.fields['chat_rate_usd'].label = 'Your chat rate per hour (USD)'
        self.fields['chat_rate_usd'].help_text = 'Choose a rate from $3 to $5 per hour.'
        self.fields['teaches_kiswahili'].label = 'Offer Kiswahili lessons'
        self.fields['lesson_rate_usd'].label = 'Your rate per two-hour Kiswahili lesson (USD)'
        self.fields['lesson_rate_usd'].help_text = 'Choose a rate from $15 to $25 per two-hour lesson.'
        self.fields['payout_method'].label = 'Preferred payout method'
        self.fields['payout_destination'].label = 'Payout phone number or PayPal email'
        self.fields['payout_destination'].help_text = 'Use the account that should receive your earnings.'

    def clean(self):
        cleaned = super().clean()
        chat_rate = cleaned.get('chat_rate_usd')
        lesson_rate = cleaned.get('lesson_rate_usd')
        if cleaned.get('offers_paid_chat') and chat_rate is not None and not 3 <= chat_rate <= 5:
            self.add_error('chat_rate_usd', 'Set a chat rate between $3 and $5 per hour.')
        if cleaned.get('teaches_kiswahili') and lesson_rate is not None and not 15 <= lesson_rate <= 25:
            self.add_error('lesson_rate_usd', 'Set a lesson rate between $15 and $25 per two-hour lesson.')
        if not cleaned.get('offers_paid_chat') and not cleaned.get('teaches_kiswahili'):
            raise forms.ValidationError('Choose at least one service to offer.')
        if not (cleaned.get('payout_destination') or '').strip():
            self.add_error('payout_destination', 'Enter the phone number or PayPal email where you want to receive payouts.')
        elif cleaned.get('payout_method') == 'paypal':
            try:
                validate_email(cleaned['payout_destination'].strip())
                cleaned['payout_destination'] = cleaned['payout_destination'].strip().lower()
            except ValidationError:
                self.add_error('payout_destination', 'Enter a valid PayPal email address.')
        else:
            phone = cleaned['payout_destination'].replace('+', '').replace(' ', '').replace('-', '')
            if len(phone) != 12 or not phone.startswith('254') or not phone.isdigit():
                self.add_error('payout_destination', 'Enter a Kenyan wallet number with country code, such as +254712345678.')
            else:
                cleaned['payout_destination'] = phone
        return cleaned

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_age(self):
        age = self.cleaned_data['age']
        if age < 18:
            raise forms.ValidationError('You must be at least 18 to create an account.')
        return age


class StkPushForm(forms.Form):
    phone_number = forms.CharField(max_length=12, help_text='Use 07XXXXXXXX or 2547XXXXXXXX.')

    def clean_phone_number(self):
        value = self.cleaned_data['phone_number'].replace(' ', '').replace('+', '')
        if value.startswith('0'):
            value = '254' + value[1:]
        if len(value) != 12 or not value.startswith(('2547', '2541')) or not value.isdigit():
            raise forms.ValidationError('Enter a valid Kenyan Safaricom number, such as 0712345678.')
        return value


class CustomerRegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=255, label='Full name')
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)
    country = forms.CharField(max_length=100)
    age = forms.IntegerField(min_value=18, label='Age')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email


class ServiceBookingForm(forms.Form):
    service_type = forms.ChoiceField(choices=[('chat', 'Paid conversation'), ('kiswahili', 'Kiswahili lesson (2 hours)')])
    scheduled_at = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label='Preferred date and time (East Africa Time)',
        help_text='Choose the time in East Africa Time (UTC+3).',
    )
    chat_hours = forms.IntegerField(min_value=1, max_value=4, initial=1, required=False, label='Conversation hours')

    def __init__(self, *args, provider=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.provider = provider

    def clean(self):
        cleaned = super().clean()
        service = cleaned.get('service_type')
        if self.provider and service == 'chat' and not self.provider.offers_paid_chat:
            self.add_error('service_type', 'This provider does not currently offer paid chat sessions.')
        if self.provider and service == 'kiswahili' and not self.provider.teaches_kiswahili:
            self.add_error('service_type', 'This provider does not currently offer Kiswahili lessons.')
        if service == 'kiswahili':
            cleaned['chat_hours'] = 2
        scheduled_at = cleaned.get('scheduled_at')
        if scheduled_at and scheduled_at <= timezone.localtime():
            self.add_error('scheduled_at', 'Choose a future date and time.')
        return cleaned


class ChatMessageForm(forms.ModelForm):
    class Meta:
        model = ChatMessage
        fields = ['body']
        widgets = {'body': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Write a kind, friendly message…'})}
        labels = {'body': 'Your message'}

    def clean_body(self):
        body = self.cleaned_data['body'].strip()
        if not body:
            raise forms.ValidationError('Write a message before sending.')
        return body


class ChatReportForm(forms.ModelForm):
    class Meta:
        model = ChatReport
        fields = ['reason']
        widgets = {'reason': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Tell our team what happened…'})}
        labels = {'reason': 'What should our team know?'}

    def clean_reason(self):
        reason = self.cleaned_data['reason'].strip()
        if not reason:
            raise forms.ValidationError('Please include a short reason for your report.')
        return reason


class ServiceMessageForm(forms.ModelForm):
    class Meta:
        model = ServiceMessage
        fields = ['body']
        widgets = {'body': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Write your message…'})}

    def clean_body(self):
        body = self.cleaned_data['body'].strip()
        if not body:
            raise forms.ValidationError('Write a message before sending.')
        return body
