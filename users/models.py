# users/models.py
from django.db import models
from django.contrib.auth.models import Permission as DjangoPermission
from django.conf import settings
import uuid

class Role(models.Model):
    """
    Custom Role model with hierarchical structure
    """
    ROLE_TYPES = [
        ('super_admin', 'Super Administrator'),
        ('admin', 'Administrator'),
        ('teacher', 'Teacher'),
        ('accountant', 'Accountant'),
        ('parent', 'Parent'),
        ('student', 'Student'),
        ('receptionist', 'Receptionist'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True, choices=ROLE_TYPES)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Hierarchical relationship
    parent_role = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='child_roles'
    )
    
    # Link to Django's permission system
    permissions = models.ManyToManyField(
        DjangoPermission,
        blank=True,
        related_name='custom_roles'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
    
    def __str__(self):
        return self.get_name_display()
    
    def get_name_display(self):
        return dict(self.ROLE_TYPES).get(self.name, self.name)
    
    def get_all_permissions(self):
        """Get all permissions including inherited ones"""
        permissions = set(self.permissions.all())
        
        # Inherit permissions from parent role
        if self.parent_role:
            permissions.update(self.parent_role.get_all_permissions())
        
        return permissions
    
    def has_permission(self, codename):
        """Check if role has a specific permission"""
        return self.permissions.filter(codename=codename).exists() or (
            self.parent_role and self.parent_role.has_permission(codename)
        )
    
    def get_all_ancestors(self):
        """Get all parent roles in hierarchy"""
        ancestors = []
        current = self.parent_role
        while current:
            ancestors.append(current)
            current = current.parent_role
        return ancestors


class UserRole(models.Model):
    """
    Many-to-many relationship between User and Role with additional metadata
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='role_users')
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='assigned_roles')
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['user', 'role']
        verbose_name = 'User Role'
        verbose_name_plural = 'User Roles'
    
    def __str__(self):
        return f"{self.user.username} - {self.role.name}"


class UserSession(models.Model):
    """
    Track user sessions for security
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sessions')
    session_token = models.CharField(max_length=255, unique=True)
    device_info = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    login_time = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-login_time']
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
    
    def __str__(self):
        return f"{self.user.username} - {self.login_time.strftime('%Y-%m-%d %H:%M')}"