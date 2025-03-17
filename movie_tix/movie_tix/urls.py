from django.contrib import admin
from django.urls import path, include
from users import views as user_views
from django.conf import settings
from django.conf.urls.static import static
from .views import simple_mail, home_view, debug_view
import logging

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
    
    # Auth URLs at root level for compatibility
    path('login/', user_views.login_view, name='login'),
    path('register/', user_views.register_view, name='register'),
    path('logout/', user_views.logout_view, name='logout'),
    
    # Debug URLs
    path('debug/', debug_view, name='debug'),
    path('simple_mail/', simple_mail, name='simple_mail'),
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