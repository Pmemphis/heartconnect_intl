from django.shortcuts import render, redirect
from .forms import RegistrationForm
from .models import Applicant
import urllib.parse

def home(request):
    return render(request, 'members/index.html') # We will create this next

def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            return redirect('payment', user_id=user.id)
    else:
        form = RegistrationForm()
    return render(request, 'members/register.html', {'form': form})

def payment(request, user_id):
    user = Applicant.objects.get(id=user_id)
    phone = "254XXXXXXXXX" # Put your M-Pesa/WhatsApp number here
    text = f"Hello, I am {user.full_name}. I just registered on HeartConnect and want to pay the $15 fee."
    whatsapp_url = f"https://wa.me/{phone}?text={urllib.parse.quote(text)}"
    
    return render(request, 'members/payment.html', {'whatsapp_url': whatsapp_url})