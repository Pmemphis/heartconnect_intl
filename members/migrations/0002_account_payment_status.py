from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('members', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='applicant',
            name='account',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='member_profile', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='applicant',
            name='mpesa_receipt',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name='applicant',
            name='status',
            field=models.CharField(choices=[('payment_pending', 'Payment pending'), ('awaiting_confirmation', 'Awaiting confirmation'), ('approved', 'Approved'), ('rejected', 'Not approved')], default='payment_pending', max_length=32),
        ),
        migrations.CreateModel(
            name='MpesaPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone_number', models.CharField(max_length=12)),
                ('amount', models.PositiveIntegerField(default=130)),
                ('merchant_request_id', models.CharField(blank=True, max_length=100)),
                ('checkout_request_id', models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ('receipt_number', models.CharField(blank=True, max_length=32)),
                ('status', models.CharField(default='initiated', max_length=20)),
                ('result_description', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('applicant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='members.applicant')),
            ],
        ),
    ]
