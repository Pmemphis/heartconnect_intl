from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('payment/<int:user_id>/', views.payment, name='payment'),
    path('account/', views.member_dashboard, name='member_dashboard'),
    path('login/', auth_views.LoginView.as_view(template_name='members/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('payments/mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
]
