from django.contrib import admin
from django.urls import path, include, re_path
from users import views as user_views
from django.conf import settings
from django.conf.urls.static import static
from .views import simple_mail, home_view, debug_view
import logging
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Configure Swagger/OpenAPI
schema_view = get_schema_view(
    openapi.Info(
        title="MovieTix API",
        default_version='v1',
        description="API for movie ticket booking system",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@movietix.local"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

logger = logging.getLogger(__name__)

# Print debug info to help diagnose URL issues
logger.info("Loading project URLconf")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_view, name='home'),
    path('landing/', user_views.landing_view, name='landing_page'),
    
    # App includes
    path('users/', include('users.urls')),
    path('movies/', include('movies.urls')),
    path('bookings/', include('bookings.urls')),
    
    # API URLs
    path('api/', include('movie_tix.api_urls')),
    
    # Auth URLs at root level for compatibility
    path('login/', user_views.login_view, name='login'),
    path('register/', user_views.register_view, name='register'),
    path('logout/', user_views.logout_view, name='logout'),
    
    # Debug URLs
    path('debug/', debug_view, name='debug'),
    path('simple_mail/', simple_mail, name='simple_mail'),
    
    # Swagger/OpenAPI documentation
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

# Log the URL patterns to help with debugging
for pattern in urlpatterns:
    logger.info(f"URL Pattern: {pattern.pattern}")

# Always serve media and static files in development
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])

# Add Debug Toolbar URLs when in debug mode
if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]