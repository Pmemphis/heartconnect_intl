from django import forms
from django.contrib.auth import get_user_model
from .models import Applicant
from .models import ChatMessage, ChatReport

class RegistrationForm(forms.ModelForm):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)

    class Meta:
        model = Applicant
        fields = [
            'full_name', 'country', 'city', 'gender', 'age', 'occupation',
            'whatsapp_number', 'pref_age', 'pref_countries', 'profile_photo',
            'introduction', 'languages', 'interests',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields([
            'full_name', 'email', 'password', 'country', 'city', 'gender', 'age',
            'occupation', 'whatsapp_number', 'languages', 'interests',
            'introduction', 'pref_countries', 'pref_age', 'profile_photo',
        ])
        self.fields['email'].label = 'Email address'
        self.fields['email'].help_text = 'We’ll use this for your confirmation and account updates.'
        self.fields['password'].label = 'Create a password'
        self.fields['password'].help_text = 'Use at least 8 characters.'
        self.fields['whatsapp_number'].label = 'WhatsApp number'
        self.fields['whatsapp_number'].help_text = 'Include your country code, for example +254712345678.'
        self.fields['pref_age'].label = 'Preferred conversation partner age range'
        self.fields['pref_age'].help_text = 'This preference is for conversation partners, not dating.'
        self.fields['pref_countries'].label = 'Countries you would like to chat with'
        self.fields['pref_countries'].help_text = 'For example: United States, United Kingdom, Canada.'
        self.fields['profile_photo'].label = 'Profile photo'
        self.fields['profile_photo'].help_text = 'Choose a clear photo of yourself.'
        self.fields['introduction'].label = 'A little about you'
        self.fields['introduction'].help_text = 'Up to 500 characters. Share the kind of friendly company you enjoy.'
        self.fields['languages'].label = 'Languages'
        self.fields['interests'].label = 'Conversation topics and interests'

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
