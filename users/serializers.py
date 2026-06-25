# users/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import Role, UserRole, UserSession
import re

User = get_user_model()

class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.StringRelatedField(many=True)
    parent_role_name = serializers.CharField(source='parent_role.name', read_only=True)
    permission_count = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Role
        fields = [
            'id', 'name', 'display_name', 'description', 
            'parent_role', 'parent_role_name', 'permissions',
            'permission_count', 'user_count', 'created_at', 
            'updated_at', 'is_active'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_permission_count(self, obj):
        return obj.permissions.count()
    
    def get_user_count(self, obj):
        return obj.userrole_set.filter(is_active=True).count()

class UserRoleSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source='role.name', read_only=True)
    role_display_name = serializers.CharField(source='role.display_name', read_only=True)
    
    class Meta:
        model = UserRole
        fields = ['id', 'user', 'role', 'role_name', 'role_display_name', 
                 'assigned_by', 'assigned_at', 'is_active']
        read_only_fields = ['id', 'assigned_at']

class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    role_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    full_name = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'password', 'confirm_password',
            'first_name', 'last_name', 'full_name', 'phone_number', 
            'user_type', 'roles', 'role_ids',
            'profile_picture', 'date_of_birth', 'address', 
            'emergency_contact', 'is_verified', 'is_active', 
            'is_superuser', 'is_staff', 'permissions', 
            'last_login', 'last_login_ip', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'last_login', 'last_login_ip', 'created_at', 'updated_at', 'permissions']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username
    
    def get_roles(self, obj):
        user_roles = obj.user_roles.filter(is_active=True).select_related('role')
        return [{
            'id': ur.role.id,
            'name': ur.role.name,
            'display_name': ur.role.display_name
        } for ur in user_roles]
    
    def get_permissions(self, obj):
        if obj.is_superuser:
            return ['*']  # All permissions
        permissions = set()
        user_roles = obj.user_roles.filter(is_active=True).select_related('role')
        for user_role in user_roles:
            for perm in user_role.role.get_all_permissions():
                permissions.add(perm.codename)
        return list(permissions)
    
    def validate(self, data):
        # Check password match
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        
        if password and confirm_password and password != confirm_password:
            raise serializers.ValidationError("Passwords don't match")
        
        return data
    
    def create(self, validated_data):
        role_ids = validated_data.pop('role_ids', [])
        confirm_password = validated_data.pop('confirm_password', None)
        password = validated_data.pop('password', None)
        
        # Create user
        user = User.objects.create(**validated_data)
        
        # Set password if provided
        if password:
            user.set_password(password)
            user.save()
        
        # Assign roles
        if role_ids:
            roles = Role.objects.filter(id__in=role_ids)
            for role in roles:
                UserRole.objects.create(
                    user=user,
                    role=role,
                    assigned_by=self.context.get('request').user if self.context.get('request') else None
                )
        
        return user
    
    def update(self, instance, validated_data):
        role_ids = validated_data.pop('role_ids', None)
        confirm_password = validated_data.pop('confirm_password', None)
        password = validated_data.pop('password', None)
        
        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Update password
        if password:
            instance.set_password(password)
        
        instance.save()
        
        # Update roles
        if role_ids is not None:
            # Deactivate old roles
            instance.user_roles.update(is_active=False)
            
            # Assign new roles
            roles = Role.objects.filter(id__in=role_ids)
            for role in roles:
                UserRole.objects.create(
                    user=instance,
                    role=role,
                    assigned_by=self.context.get('request').user if self.context.get('request') else None
                )
        
        return instance

class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            raise serializers.ValidationError('Username and password required')
        
        # Try to find user by username or email
        user = None
        try:
            if '@' in username:
                user = User.objects.get(email=username)
            else:
                user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise serializers.ValidationError('Invalid credentials')
        
        # Check password
        if not user.check_password(password):
            raise serializers.ValidationError('Invalid credentials')
        
        # Check if user is active
        if not user.is_active:
            raise serializers.ValidationError('User account is disabled')
        
        data['user'] = user
        return data

class UserChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_new_password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        if data['new_password'] != data['confirm_new_password']:
            raise serializers.ValidationError("New passwords don't match")
        return data
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect')
        return value

class UserSessionSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = UserSession
        fields = [
            'id', 'user', 'user_username', 'user_email', 
            'device_info', 'ip_address', 'user_agent',
            'login_time', 'last_activity', 'logout_time', 'is_active'
        ]
        read_only_fields = ['id', 'login_time', 'last_activity']