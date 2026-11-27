from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('members', '0002_account_payment_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='applicant',
            name='relationship_goal',
            field=models.CharField(choices=[('Marriage', 'Marriage'), ('Serious', 'Serious Relationship'), ('Friendship', 'Friendship')], default='Friendship', max_length=20),
        ),
    ]
