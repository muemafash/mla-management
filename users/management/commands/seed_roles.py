# users/management/commands/seed_roles.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from users.models import Role, UserRole

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed initial roles and permissions'
    
    def handle(self, *args, **options):
        self.stdout.write('Seeding roles and permissions...')
        
        # Get or create content type for permissions
        try:
            content_type = ContentType.objects.get(app_label='users', model='user')
        except ContentType.DoesNotExist:
            # If user content type doesn't exist, create a temporary one
            content_type, created = ContentType.objects.get_or_create(
                app_label='users',
                model='user'
            )
        
        # Create permissions for each module
        permissions_data = {
            'students': ['view_student', 'add_student', 'change_student', 'delete_student'],
            'classes': ['view_class', 'add_class', 'change_class', 'delete_class'],
            'fees': ['view_fee', 'add_fee', 'change_fee', 'delete_fee'],
            'payments': ['view_payment', 'add_payment', 'change_payment', 'delete_payment'],
            'attendance': ['view_attendance', 'add_attendance', 'change_attendance', 'delete_attendance'],
            'results': ['view_result', 'add_result', 'change_result', 'delete_result'],
            'notices': ['view_notice', 'add_notice', 'change_notice', 'delete_notice'],
            'users': ['view_user', 'add_user', 'change_user', 'delete_user'],
            'reports': ['view_financial_report', 'view_attendance_report', 'view_academic_report', 'export_report'],
        }
        
        # Create permissions
        for app_label, codenames in permissions_data.items():
            for codename in codenames:
                permission, created = Permission.objects.get_or_create(
                    codename=codename,
                    defaults={
                        'name': f'Can {codename.replace("_", " ")}',
                        'content_type': content_type
                    }
                )
                if created:
                    self.stdout.write(f'  Created permission: {codename}')
        
        # Create roles
        roles_data = {
            'super_admin': {
                'display_name': 'Super Administrator',
                'description': 'Full system access with all permissions',
            },
            'admin': {
                'display_name': 'Administrator',
                'description': 'Administrative access except system settings',
                'parent': 'super_admin',
            },
            'accountant': {
                'display_name': 'Accountant',
                'description': 'Access to financial modules only',
            },
            'teacher': {
                'display_name': 'Teacher',
                'description': 'Access to classes, attendance, and results',
            },
            'receptionist': {
                'display_name': 'Receptionist',
                'description': 'Front desk operations',
            },
            'parent': {
                'display_name': 'Parent',
                'description': 'View child information, fees, and results',
            },
            'student': {
                'display_name': 'Student',
                'description': 'View personal information and results',
            }
        }
        
        created_roles = {}
        for role_name, role_data in roles_data.items():
            role, created = Role.objects.get_or_create(
                name=role_name,
                defaults={
                    'display_name': role_data['display_name'],
                    'description': role_data['description']
                }
            )
            created_roles[role_name] = role
            
            if created:
                self.stdout.write(f'  Created role: {role_name}')
            
            # Set parent role if specified
            if 'parent' in role_data and role_data['parent'] in created_roles:
                role.parent_role = created_roles[role_data['parent']]
                role.save()
        
        # Assign permissions to roles
        all_permissions = Permission.objects.all()
        created_roles['super_admin'].permissions.set(all_permissions)
        self.stdout.write('  Assigned all permissions to Super Admin')
        
        admin_perms = Permission.objects.filter(codename__in=[
            'view_user', 'add_user', 'change_user', 'delete_user',
            'view_student', 'add_student', 'change_student',
            'view_class', 'add_class', 'change_class'
        ])
        created_roles['admin'].permissions.set(admin_perms)
        self.stdout.write('  Assigned permissions to Admin')
        
        accountant_perms = Permission.objects.filter(codename__in=[
            'view_fee', 'add_fee', 'change_fee',
            'view_payment', 'add_payment', 'change_payment',
            'view_financial_report'
        ])
        created_roles['accountant'].permissions.set(accountant_perms)
        self.stdout.write('  Assigned permissions to Accountant')
        
        teacher_perms = Permission.objects.filter(codename__in=[
            'view_class', 'view_attendance', 'add_attendance', 'change_attendance',
            'view_result', 'add_result', 'change_result'
        ])
        created_roles['teacher'].permissions.set(teacher_perms)
        self.stdout.write('  Assigned permissions to Teacher')
        
        receptionist_perms = Permission.objects.filter(codename__in=[
            'view_student', 'add_student', 'change_student',
            'view_fee', 'view_payment', 'add_payment'
        ])
        created_roles['receptionist'].permissions.set(receptionist_perms)
        self.stdout.write('  Assigned permissions to Receptionist')
        
        parent_perms = Permission.objects.filter(codename__in=[
            'view_student', 'view_fee', 'view_payment',
            'view_attendance', 'view_result', 'view_notice'
        ])
        created_roles['parent'].permissions.set(parent_perms)
        self.stdout.write('  Assigned permissions to Parent')
        
        student_perms = Permission.objects.filter(codename__in=[
            'view_attendance', 'view_result', 'view_notice'
        ])
        created_roles['student'].permissions.set(student_perms)
        self.stdout.write('  Assigned permissions to Student')
        
        # Create superuser if not exists
        if not User.objects.filter(username='admin').exists():
            admin_user = User.objects.create_superuser(
                username='admin',
                email='admin@school.com',
                password='Admin@2026!',
                first_name='System',
                last_name='Administrator'
            )
            # Add super_admin role
            UserRole.objects.create(
                user=admin_user,
                role=created_roles['super_admin'],
                assigned_by=None
            )
            self.stdout.write(self.style.SUCCESS('  Created superuser: admin'))
        else:
            self.stdout.write('  Superuser already exists')
        
        self.stdout.write(self.style.SUCCESS('✅ Roles and permissions seeded successfully!')) 
