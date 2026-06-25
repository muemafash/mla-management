# users/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, RoleViewSet, login_view
from .test_login import test_login

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='users')
router.register(r'roles', RoleViewSet, basename='roles')

urlpatterns = [
    # Test endpoint
    path('test/', test_login, name='test'),
    
    # Public login endpoint (standalone)
    path('login/', login_view, name='login'),
    
    # Custom endpoints
    path('register/', UserViewSet.as_view({'post': 'register'}), name='user-register'),
    path('me/', UserViewSet.as_view({'get': 'me'}), name='user-me'),
    path('logout/', UserViewSet.as_view({'post': 'logout'}), name='user-logout'),
    path('change-password/', UserViewSet.as_view({'post': 'change_password'}), name='change-password'),
    
    # Router endpoints (for CRUD operations)
    path('', include(router.urls)),
]