# users/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import Role, UserRole, UserSession
from .serializers import (
    UserSerializer, RoleSerializer, UserLoginSerializer,
    UserChangePasswordSerializer, UserSessionSerializer
)
import uuid
import json

User = get_user_model()

class UserViewSet(viewsets.ModelViewSet):
    """
    User management with role-based access control
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by user type
        user_type = self.request.query_params.get('user_type')
        if user_type:
            queryset = queryset.filter(user_type=user_type)
        
        # Filter by role
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(user_roles__role__name=role, user_roles__is_active=True)
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(phone_number__icontains=search)
            )
        
        # Filter by status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        # Only admins can list all users
        if not (request.user.is_superuser or self.has_user_permission(request.user, 'view_user')):
            return Response(
                {'error': 'Permission denied to view users'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().list(request, *args, **kwargs)
    
    def create(self, request, *args, **kwargs):
        # Only admins can create users
        if not (request.user.is_superuser or self.has_user_permission(request.user, 'add_user')):
            return Response(
                {'error': 'Permission denied to create users'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)
    
    def has_user_permission(self, user, codename):
        """Check if user has permission through roles"""
        if user.is_superuser:
            return True
        user_roles = user.user_roles.filter(is_active=True).select_related('role')
        for user_role in user_roles:
            if user_role.role.has_permission(codename):
                return True
        return False
    
    @action(detail=False, methods=['post'], authentication_classes=[], permission_classes=[])
    def register(self, request):
        """
        Public registration endpoint (self-registration)
        """
        serializer = UserSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.save()
            
            # Assign default role based on user type
            role_name = 'student' if user.user_type == 'student' else 'parent'
            try:
                role = Role.objects.get(name=role_name)
                UserRole.objects.create(
                    user=user,
                    role=role,
                    assigned_by=None  # Self-registration
                )
            except Role.DoesNotExist:
                pass
            
            # Create refresh token
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'message': 'User registered successfully',
                'user': UserSerializer(user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], authentication_classes=[], permission_classes=[])
    def login(self, request):
        """
        User login endpoint
        """
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            # Update last login
            user.last_login = timezone.now()
            user.last_login_ip = self.get_client_ip(request)
            user.save(update_fields=['last_login', 'last_login_ip'])
            
            # Create session
            session_token = str(uuid.uuid4())
            UserSession.objects.create(
                user=user,
                session_token=session_token,
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                device_info={
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'ip': self.get_client_ip(request),
                }
            )
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            # Get user permissions
            permissions = []
            if user.is_superuser:
                permissions = ['*']
            else:
                user_roles = user.user_roles.filter(is_active=True).select_related('role')
                for user_role in user_roles:
                    for perm in user_role.role.get_all_permissions():
                        permissions.append(perm.codename)
            
            return Response({
                'message': 'Login successful',
                'user': UserSerializer(user).data,
                'permissions': permissions,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                },
                'session_token': session_token
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def logout(self, request):
        """
        User logout - invalidate session
        """
        session_token = request.data.get('session_token')
        if session_token:
            try:
                session = UserSession.objects.get(
                    session_token=session_token,
                    user=request.user,
                    is_active=True
                )
                session.is_active = False
                session.logout_time = timezone.now()
                session.save()
            except UserSession.DoesNotExist:
                pass
        
        return Response({'message': 'Logged out successfully'})
    
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """
        Change user password
        """
        serializer = UserChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({'message': 'Password changed successfully'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Get current user profile
        """
        user = request.user
        
        # Get user roles
        roles = []
        user_roles = user.user_roles.filter(is_active=True).select_related('role')
        for ur in user_roles:
            roles.append({
                'id': str(ur.role.id),
                'name': ur.role.name,
                'display_name': ur.role.display_name
            })
        
        # Get user permissions
        permissions = []
        if user.is_superuser:
            permissions = ['*']
        else:
            for ur in user_roles:
                for perm in ur.role.get_all_permissions():
                    permissions.append(perm.codename)
        
        return Response({
            'id': str(user.id),
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.get_full_name(),
            'user_type': getattr(user, 'user_type', 'staff'),
            'phone_number': getattr(user, 'phone_number', ''),
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
            'is_active': user.is_active,
            'is_verified': getattr(user, 'is_verified', False),
            'last_login': user.last_login,
            'date_joined': user.date_joined,
            'roles': roles,
            'permissions': permissions,
        })
    
    @action(detail=True, methods=['post'])
    def assign_role(self, request, pk=None):
        """
        Assign role to a user
        """
        user = self.get_object()
        
        if not (request.user.is_superuser or self.has_user_permission(request.user, 'change_user')):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        role_id = request.data.get('role_id')
        if not role_id:
            return Response(
                {'error': 'role_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            role = Role.objects.get(id=role_id)
            
            # Check if already assigned
            user_role, created = UserRole.objects.get_or_create(
                user=user,
                role=role,
                defaults={
                    'assigned_by': request.user,
                    'is_active': True
                }
            )
            
            if not created and not user_role.is_active:
                user_role.is_active = True
                user_role.assigned_by = request.user
                user_role.save()
            
            return Response({
                'message': f'Role {role.name} assigned successfully',
                'user': UserSerializer(user).data
            })
        except Role.DoesNotExist:
            return Response(
                {'error': 'Role not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def remove_role(self, request, pk=None):
        """
        Remove role from a user
        """
        user = self.get_object()
        
        if not (request.user.is_superuser or self.has_user_permission(request.user, 'change_user')):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        role_id = request.data.get('role_id')
        if not role_id:
            return Response(
                {'error': 'role_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            role = Role.objects.get(id=role_id)
            user_role = UserRole.objects.get(user=user, role=role)
            user_role.is_active = False
            user_role.save()
            
            return Response({
                'message': f'Role {role.name} removed successfully',
                'user': UserSerializer(user).data
            })
        except Role.DoesNotExist:
            return Response(
                {'error': 'Role not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except UserRole.DoesNotExist:
            return Response(
                {'error': 'User does not have this role'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class RoleViewSet(viewsets.ModelViewSet):
    """
    Role management
    """
    queryset = Role.objects.filter(is_active=True)
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_permissions(self):
        # Only superusers or admins can manage roles
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [permissions.IsAdminUser]
        return super().get_permissions()
    
    @action(detail=False, methods=['get'])
    def available_permissions(self, request):
        """
        Get all available permissions
        """
        from django.contrib.auth.models import Permission
        
        permissions = Permission.objects.all().values('codename', 'name', 'content_type__app_label')
        
        # Group by module
        grouped = {}
        for perm in permissions:
            module = perm['content_type__app_label']
            if module not in grouped:
                grouped[module] = []
            grouped[module].append({
                'codename': perm['codename'],
                'name': perm['name']
            })
        
        return Response(grouped)
    
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """
        Get users with this role
        """
        role = self.get_object()
        users = User.objects.filter(user_roles__role=role, user_roles__is_active=True)
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)


# Standalone login view - FULL VERSION WITH JWT
@csrf_exempt
def login_view(request):
    """Simple login view that returns JWT tokens"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception as e:
        return JsonResponse({'error': 'Invalid JSON', 'details': str(e)}, status=400)
    
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return JsonResponse({'error': 'Username and password required'}, status=400)
    
    # Try to find user by username or email
    try:
        if '@' in username:
            user = User.objects.get(email=username)
        else:
            user = User.objects.get(username=username)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Invalid credentials'}, status=401)
    
    if not user.check_password(password):
        return JsonResponse({'error': 'Invalid credentials'}, status=401)
    
    if not user.is_active:
        return JsonResponse({'error': 'User account is disabled'}, status=401)
    
    # Update last login
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])
    
    # Generate JWT tokens
    refresh = RefreshToken.for_user(user)
    
    # Get user permissions
    permissions = []
    if user.is_superuser:
        permissions = ['*']
    else:
        user_roles = user.user_roles.filter(is_active=True).select_related('role')
        for user_role in user_roles:
            for perm in user_role.role.get_all_permissions():
                permissions.append(perm.codename)
    
    # Create session
    session_token = str(uuid.uuid4())
    try:
        UserSession.objects.create(
            user=user,
            session_token=session_token,
            ip_address=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            device_info={
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'ip': request.META.get('REMOTE_ADDR', ''),
            }
        )
    except Exception as e:
        # Session creation failed but login should still work
        pass
    
    return JsonResponse({
        'message': 'Login successful',
        'user': {
            'id': str(user.id),
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'user_type': getattr(user, 'user_type', 'staff'),
        },
        'permissions': permissions,
        'tokens': {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        },
        'session_token': session_token
    })