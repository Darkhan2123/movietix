from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserRole(models.Model):

    ROLE_CUSTOMER = 'customer'
    ROLE_THEATER = 'theater'
    ROLE_ADMIN = 'admin'

    ROLE_CHOICES = [
        (ROLE_CUSTOMER, 'Customer'),
        (ROLE_THEATER, 'Theater Manager'),
        (ROLE_ADMIN, 'Administrator'),
    ]

    name = models.CharField(max_length=30, choices=ROLE_CHOICES, unique=True)
    description = models.CharField(max_length=255)

    def __str__(self):
        return self.get_name_display()

class Profile(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    profile_picture = models.ImageField(
        upload_to='profile_pictures/', blank=True, null=True, default='default.jpg'
    )
    email_verified = models.BooleanField(default=False)
    role = models.ForeignKey(UserRole, on_delete=models.SET_NULL, null=True, blank=True, related_name='profiles')

    is_student = models.BooleanField(default=False)
    student_id_verified = models.BooleanField(default=False)
    student_id_number = models.CharField(max_length=50, blank=True, null=True)

    # Additional info
    bio = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    def __str__(self):
        return f'{self.user.username} Profile'

    @property
    def is_admin(self):
        return self.role and self.role.name == UserRole.ROLE_ADMIN

    @property
    def is_theater_manager(self):
        return self.role and self.role.name == UserRole.ROLE_THEATER

    @property
    def is_customer(self):
        return not self.role or self.role.name == UserRole.ROLE_CUSTOMER


@receiver(post_save, sender=User)
def manage_user_profile(sender, instance, created, **kwargs):
    customer_role, _ = UserRole.objects.get_or_create(
        name=UserRole.ROLE_CUSTOMER,
        defaults={'description': 'Regular user who can book tickets'}
    )

    profile, profile_created = Profile.objects.get_or_create(
        user=instance,
        defaults={'role': customer_role}
    )

    if not profile.role:
        profile.role = customer_role
        profile.save()