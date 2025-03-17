from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from users.models import UserRole, Profile
import getpass
import sys

class Command(BaseCommand):
    help = 'Create a user with a specified role'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username')
        parser.add_argument('email', type=str, help='Email address')
        parser.add_argument('--role', type=str, choices=['customer', 'theater', 'admin'], default='customer', 
                            help='User role: customer, theater, or admin')
        parser.add_argument('--first_name', type=str, help='First name')
        parser.add_argument('--last_name', type=str, help='Last name')
        parser.add_argument('--password', type=str, help='Password (not recommended, use interactive)')
        parser.add_argument('--interactive', action='store_true', help='Prompt for password interactively')
        parser.add_argument('--is_student', action='store_true', help='Mark user as a student')
        parser.add_argument('--student_id', type=str, help='Student ID number')
        parser.add_argument('--phone', type=str, help='Phone number')
        parser.add_argument('--address', type=str, help='Address')
        parser.add_argument('--verified', action='store_true', help='Mark email as verified')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        role_name = options['role']
        
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.ERROR(f'User {username} already exists'))
            return
            
        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.ERROR(f'Email {email} already exists'))
            return
            
        # Get or create role
        role, created = UserRole.objects.get_or_create(
            name=role_name,
            defaults={'description': f'{role_name.capitalize()} role'}
        )
        
        # Get password
        password = options['password']
        if options['interactive'] or not password:
            password = getpass.getpass('Password: ')
            password_confirm = getpass.getpass('Confirm password: ')
            if password != password_confirm:
                self.stdout.write(self.style.ERROR('Passwords do not match'))
                return
                
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=options['first_name'] or '',
            last_name=options['last_name'] or ''
        )
        
        # Update profile
        profile = user.profile
        profile.role = role
        profile.is_student = options['is_student']
        profile.student_id_number = options['student_id'] or ''
        profile.phone_number = options['phone'] or ''
        profile.address = options['address'] or ''
        profile.email_verified = options['verified']
        profile.save()
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {role_name} user: {username}'))