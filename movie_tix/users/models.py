from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserRole(models.Model):
    """User roles for different access levels"""
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('theater', 'Theater Manager'),
        ('admin', 'Administrator'),
    ]
    
    name = models.CharField(max_length=30, choices=ROLE_CHOICES, unique=True)
    description = models.CharField(max_length=255)
    
    def __str__(self):
        return self.get_name_display()

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True, default='default.jpg')
    email_verified = models.BooleanField(default=False)
    role = models.ForeignKey(UserRole, on_delete=models.SET_NULL, null=True, blank=True, related_name='profiles')
    
    # Student verification
    is_student = models.BooleanField(default=False)
    student_id_verified = models.BooleanField(default=False)
    student_id_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Additional profile information
    bio = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f'{self.user.username} Profile'
    
    @property
    def is_admin(self):
        return self.role and self.role.name == 'admin'
    
    @property
    def is_theater_manager(self):
        return self.role and self.role.name == 'theater'
    
    @property
    def is_customer(self):
        return not self.role or self.role.name == 'customer'

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Get or create the default customer role
        customer_role, _ = UserRole.objects.get_or_create(
            name='customer',
            defaults={'description': 'Regular user who can book tickets'}
        )
        Profile.objects.create(user=instance, role=customer_role)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except Profile.DoesNotExist:
        customer_role, _ = UserRole.objects.get_or_create(
            name='customer',
            defaults={'description': 'Regular user who can book tickets'}
        )
        Profile.objects.create(user=instance, role=customer_role)
