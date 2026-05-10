from django.contrib import admin
from django.utils.html import format_html
from .models import Applicant

@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    # This defines what columns you see in the main list
    list_display = ('thumbnail', 'full_name', 'country', 'gender', 'age', 'is_paid', 'created_at')
    
    # These filters appear on the right side for quick sorting
    list_filter = ('is_paid', 'gender', 'relationship_goal', 'country', 'has_kids')
    
    # Search bar to find users by name or phone
    search_fields = ('full_name', 'whatsapp_number', 'occupation')
    
    # Making the 'is_paid' field clickable directly from the list for speed
    list_editable = ('is_paid',)

    # Function to show a small profile picture in the admin list
    def thumbnail(self, obj):
        if obj.profile_photo:
            return format_html('<img src="{}" style="width: 45px; height:45px; border-radius:50%; object-fit:cover;" />', obj.profile_photo.url)
        return "No Photo"
    
    thumbnail.short_description = 'Photo'

# Customize the Admin Header
admin.site.site_header = "HeartConnect International Admin"
admin.site.site_title = "HeartConnect Portal"
admin.site.index_title = "Matchmaking Management"