from django import forms
from .models import Applicant

class RegistrationForm(forms.ModelForm):
    class Meta:
        model = Applicant
        fields = '__all__'
        exclude = ['is_paid', 'created_at'] # We don't want users to check "is_paid" themselves!