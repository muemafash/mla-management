# attendance/management/commands/seed_attendance_permissions.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from users.models import Role
from attendance.models import Attendance

class Command(BaseCommand):
    help = 'Seed attendance permissions'
    
    def handle(self, *args, **options):
        self.stdout.write('Seeding attendance permissions...')
        
        try:
            # Get content type for Attendance model
            content_type = ContentType.objects.get_for_model(Attendance)
            
            # Define permissions
            permissions_data = [
                ('view_attendance', 'Can view attendance'),
                ('add_attendance', 'Can add attendance'),
                ('change_attendance', 'Can change attendance'),
                ('delete_attendance', 'Can delete attendance'),
                ('view_attendance_report', 'Can view attendance report'),
            ]
            
            created_permissions = []
            for codename, name in permissions_data:
                # Use get_or_create to avoid duplicates
                permission, created = Permission.objects.get_or_create(
                    codename=codename,
                    content_type=content_type,
                    defaults={'name': name}
                )
                # If it already exists but with different name, update it
                if not created and permission.name != name:
                    permission.name = name
                    permission.save()
                    self.stdout.write(f'  Updated permission: {codename}')
                elif created:
                    self.stdout.write(f'  Created permission: {codename}')
                else:
                    self.stdout.write(f'  Permission already exists: {codename}')
                created_permissions.append(permission)
            
            # Get or create roles
            roles_data = [
                ('teacher', ['view_attendance', 'add_attendance', 'change_attendance', 'delete_attendance', 'view_attendance_report']),
                ('parent', ['view_attendance', 'view_attendance_report']),
                ('student', ['view_attendance']),
                ('admin', ['view_attendance', 'add_attendance', 'change_attendance', 'delete_attendance', 'view_attendance_report']),
            ]
            
            for role_name, perm_codenames in roles_data:
                try:
                    role = Role.objects.get(name=role_name)
                    perms = Permission.objects.filter(codename__in=perm_codenames, content_type=content_type)
                    role.permissions.add(*perms)
                    self.stdout.write(f'  Assigned attendance permissions to {role_name.capitalize()}')
                except Role.DoesNotExist:
                    self.stdout.write(f'  Role "{role_name}" not found, skipping...')
            
            self.stdout.write(self.style.SUCCESS('✅ Attendance permissions seeded successfully!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))
            import traceback
            traceback.print_exc()