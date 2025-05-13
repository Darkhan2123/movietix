from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Profile, UserRole

class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = ['id', 'name', 'description']

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined']

class ProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    role = UserRoleSerializer(read_only=True)
    
    class Meta:
        model = Profile
        fields = ['id', 'user', 'phone_number', 'address', 'profile_picture', 
                 'email_verified', 'role', 'is_student', 'student_id_verified',
                 'student_id_number', 'bio', 'date_of_birth']