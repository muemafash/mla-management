# students/middleware.py
from django.utils.deprecation import MiddlewareMixin

class DisableCSRFForAPI(MiddlewareMixin):
    """Disable CSRF for API endpoints"""
    
    def process_request(self, request):
        if request.path.startswith('/api/'):
            # Disable CSRF for all API endpoints
            setattr(request, '_dont_enforce_csrf', True)