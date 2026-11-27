from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('customer/register/', views.customer_register, name='customer_register'),
    path('payment/<int:user_id>/', views.payment, name='payment'),
    path('checkout/<int:payment_id>/', views.checkout_options, name='checkout_options'),
    path('checkout/<int:payment_id>/<str:provider>/', views.checkout_start, name='checkout_start'),
    path('payments/cancelled/', views.payment_cancelled, name='payment_cancelled'),
    path('payments/paypal/return/', views.paypal_return, name='paypal_return'),
    path('payments/stripe/return/', views.stripe_return, name='stripe_return'),
    path('payments/stripe/webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('customer/account/', views.customer_dashboard, name='customer_dashboard'),
    path('customer/book/<int:provider_id>/', views.book_service, name='book_service'),
    path('bookings/<int:booking_id>/chat/', views.service_chat, name='service_chat'),
    path('bookings/<int:booking_id>/complete/', views.complete_booking, name='complete_booking'),
    path('account/home/', views.account_home, name='account_home'),
    path('account/', views.member_dashboard, name='member_dashboard'),
    path('community/', views.member_directory, name='member_directory'),
    path('inbox/', views.inbox, name='inbox'),
    path('chat/start/<int:member_id>/', views.start_conversation, name='start_conversation'),
    path('chat/<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),
    path('chat/<int:conversation_id>/updates/', views.conversation_updates, name='conversation_updates'),
    path('chat/<int:conversation_id>/safety/', views.conversation_safety, name='conversation_safety'),
    path('login/', auth_views.LoginView.as_view(template_name='members/login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('payments/mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
]
