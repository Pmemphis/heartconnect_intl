from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('payment/<int:user_id>/', views.payment, name='payment'),
    path('account/', views.member_dashboard, name='member_dashboard'),
    path('community/', views.member_directory, name='member_directory'),
    path('inbox/', views.inbox, name='inbox'),
    path('chat/start/<int:member_id>/', views.start_conversation, name='start_conversation'),
    path('chat/<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),
    path('chat/<int:conversation_id>/updates/', views.conversation_updates, name='conversation_updates'),
    path('chat/<int:conversation_id>/safety/', views.conversation_safety, name='conversation_safety'),
    path('login/', auth_views.LoginView.as_view(template_name='members/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('payments/mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
]
