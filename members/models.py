from django.db import models

class Applicant(models.Model):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female')]
    GOAL_CHOICES = [('Marriage', 'Marriage'), ('Serious', 'Serious Relationship'), ('Friendship', 'Friendship')]
    
    # Personal Details
    full_name = models.CharField(max_length=255)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    age = models.PositiveIntegerField()
    occupation = models.CharField(max_length=255)
    whatsapp_number = models.CharField(max_length=20)
    
    # Family info
    has_kids = models.BooleanField(default=False)
    kids_info = models.TextField(blank=True, null=True)
    
    # Preferences
    pref_age = models.CharField(max_length=50)
    pref_countries = models.CharField(max_length=255)
    relationship_goal = models.CharField(max_length=20, choices=GOAL_CHOICES)
    
    profile_photo = models.ImageField(upload_to='profiles/')
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name