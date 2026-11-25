from django import forms
from django.contrib.auth import get_user_model
from .models import Applicant

class RegistrationForm(forms.ModelForm):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)

    class Meta:
        model = Applicant
        fields = [
            'full_name', 'country', 'city', 'gender', 'age', 'occupation',
            'whatsapp_number', 'has_kids', 'kids_info', 'pref_age',
            'pref_countries', 'relationship_goal', 'profile_photo',
        ]

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
