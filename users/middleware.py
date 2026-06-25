# users/middleware.py
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from .models import UserSession
import json
from datetime import datetime

User = get_user_model()

class RolePermissionMiddleware:
    """
    Middleware to check role-based permissions for API endpoints
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Define which modules require which permissions
        self.module_permissions = {
            'students': ['view_student', 'add_student', 'change_student', 'delete_student'],
            'classes': ['view_class', 'add_class', 'change_class', 'delete_class'],
            'fees': ['view_fee', 'add_fee', 'change_fee', 'delete_fee'],
            'payments': ['view_payment', 'add_payment', 'change_payment', 'delete_payment'],
            'attendance': ['view_attendance', 'add_attendance', 'change_attendance', 'delete_attendance'],
            'results': ['view_result', 'add_result', 'change_result', 'delete_result'],
            'notices': ['view_notice', 'add_notice', 'change_notice', 'delete_notice'],
            'users': ['view_user', 'add_user', 'change_user', 'delete_user'],
            'reports': ['view_financial_report', 'view_attendance_report', 'view_academic_report'],
        }
        
        # Map HTTP methods to permissions
        self.method_map = {
            'GET': 'view',
            'POST': 'add',
            'PUT': 'change',
            'PATCH': 'change',
            'DELETE': 'delete',
        }
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Skip permission checks for certain paths
        skip_paths = ['/api/users/login/', '/api/users/register/', '/admin/', '/media/', '/static/', '/api/token/']
        if any(request.path.startswith(path) for path in skip_paths):
            return None
        
        # Only check API endpoints
        if not request.path.startswith('/api/'):
            return None
        
        # Skip for authenticated admin users
        if request.user.is_authenticated and request.user.is_superuser:
            return None
        
        # Skip if user is not authenticated
        if not request.user.is_authenticated:
            return JsonResponse({
                'error': 'Authentication required',
                'code': 'AUTH_REQUIRED'
            }, status=401)
        
        # Determine module from URL
        url_parts = request.path.split('/')
        if len(url_parts) < 3:
            return None
        
        module = url_parts[2]  # /api/students/ -> students
        
        # Check if module requires permissions
        if module not in self.module_permissions:
            return None
        
        # Get required permission based on HTTP method
        method = request.method
        action = self.method_map.get(method, 'view')
        required_permission = f'{action}_{module}'
        
        # Check if user has the required permission through roles
        if not self.user_has_permission(request.user, required_permission):
            return JsonResponse({
                'error': 'Permission denied',
                'required_permission': required_permission,
                'user_roles': [ur.role.name for ur in request.user.user_roles.filter(is_active=True)],
                'code': 'PERMISSION_DENIED'
            }, status=403)
        
        return None
    
    def user_has_permission(self, user, codename):
        """Check if user has permission through roles"""
        if user.is_superuser:
            return True
        user_roles = user.user_roles.filter(is_active=True).select_related('role')
        for user_role in user_roles:
            if user_role.role.has_permission(codename):
                return True
        return False

class SessionTrackingMiddleware:
    """
    Track user sessions for security monitoring
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Track user activity
        if request.user.is_authenticated:
            # Update last activity
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header.startswith('Bearer '):
                session_token = auth_header.replace('Bearer ', '')
                try:
                    session = UserSession.objects.get(session_token=session_token, is_active=True)
                    session.last_activity = datetime.now()
                    session.save(update_fields=['last_activity'])
                except UserSession.DoesNotExist:
                    pass
        
        response = self.get_response(request)
        return response