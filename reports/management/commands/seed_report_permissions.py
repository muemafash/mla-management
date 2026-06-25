# reports/management/commands/seed_report_permissions.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from users.models import Role
from reports.models import Report

class Command(BaseCommand):
    help = 'Seed report permissions'
    
    def handle(self, *args, **options):
        self.stdout.write('Seeding report permissions...')
        
        try:
            content_type = ContentType.objects.get_for_model(Report)
            
            permissions_data = [
                ('view_report', 'Can view reports'),
                ('generate_report', 'Can generate reports'),
                ('view_financial_report', 'Can view financial reports'),
                ('view_attendance_report', 'Can view attendance reports'),
                ('view_academic_report', 'Can view academic reports'),
                ('export_report', 'Can export reports'),
            ]
            
            created_permissions = []
            for codename, name in permissions_data:
                permission, created = Permission.objects.get_or_create(
                    codename=codename,
                    content_type=content_type,
                    defaults={'name': name}
                )
                created_permissions.append(permission)
                if created:
                    self.stdout.write(f'  Created permission: {codename}')
            
            # Assign to roles
            roles_data = [
                ('admin', ['view_report', 'generate_report', 'view_financial_report', 
                          'view_attendance_report', 'view_academic_report', 'export_report']),
                ('teacher', ['view_attendance_report', 'view_academic_report']),
                ('parent', ['view_attendance_report']),
                ('student', ['view_academic_report']),
            ]
            
            for role_name, perm_codenames in roles_data:
                try:
                    role = Role.objects.get(name=role_name)
                    perms = Permission.objects.filter(codename__in=perm_codenames)
                    role.permissions.add(*perms)
                    self.stdout.write(f'  Assigned report permissions to {role_name.capitalize()}')
                except Role.DoesNotExist:
                    self.stdout.write(f'  Role "{role_name}" not found, skipping...')
            
            self.stdout.write(self.style.SUCCESS('✅ Report permissions seeded successfully!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))