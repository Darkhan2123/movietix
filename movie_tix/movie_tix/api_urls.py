from django.urls import path, include
from rest_framework.routers import DefaultRouter
from movies.api_views import MovieViewSet
from bookings.api_views import TheaterViewSet, ShowtimeViewSet, SeatViewSet, BookingViewSet
from users.api_views import UserViewSet, ProfileViewSet, UserRoleViewSet
from users.auth_api_views import LoginView, LogoutView, RegisterView, CustomAuthToken

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'movies', MovieViewSet)
router.register(r'theaters', TheaterViewSet)
router.register(r'showtimes', ShowtimeViewSet)
router.register(r'seats', SeatViewSet)
router.register(r'bookings', BookingViewSet)
router.register(r'users', UserViewSet)
router.register(r'profiles', ProfileViewSet)
router.register(r'roles', UserRoleViewSet)

# The API URLs are determined automatically by the router
urlpatterns = [
    path('', include(router.urls)),
    # Authentication endpoints
    path('auth/login/', LoginView.as_view(), name='api-login'),
    path('auth/logout/', LogoutView.as_view(), name='api-logout'),
    path('auth/register/', RegisterView.as_view(), name='api-register'),
    path('auth/token/', CustomAuthToken.as_view(), name='api-token'),
    # DRF browsable API authentication
    path('auth/', include('rest_framework.urls', namespace='rest_framework')),
]