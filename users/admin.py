# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from .models import Role, UserRole, UserSession

User = get_user_model()

# Extend the existing UserAdmin
class UserAdminExtended(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    
    # Add roles to the fieldsets
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Roles & Permissions', {
            'fields': ('get_roles_display',),
            'description': 'User roles manage permissions'
        }),
    )
    
    readonly_fields = ('get_roles_display',)
    
    def get_roles_display(self, obj):
        roles = obj.user_roles.filter(is_active=True)
        return ", ".join([ur.role.display_name for ur in roles])
    get_roles_display.short_description = 'Roles'

# Re-register User admin if it's already registered
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, UserAdminExtended)

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'parent_role', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'display_name', 'description')
    filter_horizontal = ('permissions',)
    readonly_fields = ('id', 'created_at', 'updated_at')

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'assigned_by', 'assigned_at', 'is_active')
    list_filter = ('is_active', 'assigned_at')
    search_fields = ('user__username', 'role__name')
    readonly_fields = ('assigned_at',)

@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'login_time', 'last_activity', 'is_active', 'ip_address')
    list_filter = ('is_active', 'login_time')
    search_fields = ('user__username', 'user__email', 'ip_address')
    readonly_fields = ('id', 'login_time', 'last_activity')