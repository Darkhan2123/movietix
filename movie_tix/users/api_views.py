from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from .models import Profile, UserRole
from .serializers import UserSerializer, ProfileSerializer, UserRoleSerializer


class IsOwnerOrStaffOrReadOnly(permissions.BasePermission):
    """
    Custom permission to allow object access only to owner or staff.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if hasattr(obj, 'user'):
            return obj.user == request.user or request.user.is_staff
        return obj == request.user or request.user.is_staff


class BaseRestrictedViewSet(viewsets.ModelViewSet):
    """
    Base class for viewsets with queryset filtering for non-staff users.
    Assumes model has `user` field related to `auth.User`.
    """
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrStaffOrReadOnly]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(user=self.request.user)


class UserViewSet(BaseRestrictedViewSet):
    """
    API endpoint for users.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_queryset(self):
        if self.request.user.is_staff:
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)

    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class ProfileViewSet(BaseRestrictedViewSet):
    """
    API endpoint for user profiles.
    """
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer

    @action(detail=False, methods=['get'])
    def my_profile(self, request):
        try:
            profile = Profile.objects.get(user=request.user)
        except Profile.DoesNotExist:
            return Response(
                {"detail": "Profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(profile)
        return Response(serializer.data)


class UserRoleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for user roles (read-only).
    """
    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [permissions.IsAuthenticated]