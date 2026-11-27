from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('members', '0003_chat_service_profile'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='applicant', name='introduction',
            field=models.TextField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='applicant', name='languages',
            field=models.CharField(blank=True, help_text='Languages you can chat in, separated by commas.', max_length=255),
        ),
        migrations.AddField(
            model_name='applicant', name='interests',
            field=models.CharField(blank=True, help_text='Topics you enjoy, separated by commas.', max_length=255),
        ),
        migrations.CreateModel(
            name='Conversation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('member_one', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversations_as_one', to='members.applicant')),
                ('member_two', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversations_as_two', to='members.applicant')),
            ],
            options={'ordering': ['-updated_at']},
        ),
        migrations.AddConstraint(
            model_name='conversation', constraint=models.UniqueConstraint(fields=('member_one', 'member_two'), name='unique_member_conversation'),
        ),
        migrations.AddConstraint(
            model_name='conversation', constraint=models.CheckConstraint(condition=~models.Q(('member_one', models.F('member_two'))), name='conversation_members_differ'),
        ),
        migrations.CreateModel(
            name='ChatMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField(max_length=2000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='members.conversation')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_chat_messages', to='members.applicant')),
            ],
            options={'ordering': ['created_at']},
        ),
        migrations.CreateModel(
            name='MemberBlock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('blocked', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='blocks_received', to='members.applicant')),
                ('blocker', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='blocks_made', to='members.applicant')),
            ],
        ),
        migrations.AddConstraint(
            model_name='memberblock', constraint=models.UniqueConstraint(fields=('blocker', 'blocked'), name='unique_member_block'),
        ),
        migrations.AddConstraint(
            model_name='memberblock', constraint=models.CheckConstraint(condition=~models.Q(('blocker', models.F('blocked'))), name='member_cannot_block_self'),
        ),
        migrations.CreateModel(
            name='ChatReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField(max_length=1000)),
                ('status', models.CharField(choices=[('open', 'Open'), ('reviewed', 'Reviewed'), ('closed', 'Closed')], default='open', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('conversation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reports', to='members.conversation')),
                ('reported', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_reports_received', to='members.applicant')),
                ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_reports_made', to='members.applicant')),
            ],
        ),
    ]
