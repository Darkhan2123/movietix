from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.settings import api_settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from .serializers import UserSerializer
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

# === Reusable Swagger Schemas === #
login_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=['username', 'password'],
    properties={
        'username': openapi.Schema(type=openapi.TYPE_STRING),
        'password': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD),
    }
)

register_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=['username', 'password', 'email', 'password_confirmation'],
    properties={
        'username': openapi.Schema(type=openapi.TYPE_STRING),
        'email': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL),
        'password': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD),
        'password_confirmation': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD),
        'first_name': openapi.Schema(type=openapi.TYPE_STRING),
        'last_name': openapi.Schema(type=openapi.TYPE_STRING),
    }
)

# === Utility Functions === #
def validate_registration_data(data):
    required_fields = ['username', 'email', 'password', 'password_confirmation']
    for field in required_fields:
        if not data.get(field):
            return f"{field} is required"

    if data['password'] != data['password_confirmation']:
        return "Passwords do not match"

    if User.objects.filter(username=data['username']).exists():
        return "Username already exists"

    if User.objects.filter(email=data['email']).exists():
        return "Email already exists"

    return None

# === Views === #
class CustomAuthToken(ObtainAuthToken):
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES

    @swagger_auto_schema(
        operation_description="Get API token with username and password",
        request_body=login_schema,
        responses={
            200: openapi.Response(
                description="Token created successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'token': openapi.Schema(type=openapi.TYPE_STRING),
                        'user_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'email': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: "Bad request",
            401: "Invalid credentials"
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'email': user.email
        })

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_description="Login with username and password",
        request_body=login_schema,
        responses={200: UserSerializer, 400: "Bad request", 401: "Invalid credentials"}
    )
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({"error": "Username and password are required"}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)
        if not user:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        login(request, user)
        return Response(UserSerializer(user).data)

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Logout the current user",
        responses={200: openapi.Response(description="Successfully logged out"), 401: "Not authenticated"}
    )
    def post(self, request):
        logout(request)
        return Response({"message": "Successfully logged out"}, status=status.HTTP_200_OK)

class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_description="Register a new user",
        request_body=register_schema,
        responses={201: UserSerializer, 400: "Bad request"}
    )
    def post(self, request):
        error = validate_registration_data(request.data)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            username=request.data['username'],
            email=request.data['email'],
            password=request.data['password'],
            first_name=request.data.get('first_name', ''),
            last_name=request.data.get('last_name', '')
        )

        login(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
