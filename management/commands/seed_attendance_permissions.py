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
        
        # Get content type for Attendance model
        content_type = ContentType.objects.get_for_model(Attendance)
        
        # Create permissions
        permissions_data = [
            ('view_attendance', 'Can view attendance'),
            ('add_attendance', 'Can add attendance'),
            ('change_attendance', 'Can change attendance'),
            ('delete_attendance', 'Can delete attendance'),
            ('view_attendance_report', 'Can view attendance report'),
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
        
        # Assign permissions to roles
        try:
            # Teacher gets all attendance permissions
            teacher_role = Role.objects.get(name='teacher')
            teacher_role.permissions.add(*created_permissions)
            self.stdout.write('  Assigned attendance permissions to Teacher')
            
            # Parent gets view permissions
            parent_role = Role.objects.get(name='parent')
            parent_role.permissions.add(
                Permission.objects.get(codename='view_attendance'),
                Permission.objects.get(codename='view_attendance_report')
            )
            self.stdout.write('  Assigned view permissions to Parent')
            
            # Student gets view own attendance
            student_role = Role.objects.get(name='student')
            student_role.permissions.add(
                Permission.objects.get(codename='view_attendance')
            )
            self.stdout.write('  Assigned view permissions to Student')
            
            # Admin gets all permissions
            admin_role = Role.objects.get(name='admin')
            admin_role.permissions.add(*created_permissions)
            self.stdout.write('  Assigned attendance permissions to Admin')
            
        except Role.DoesNotExist as e:
            self.stdout.write(self.style.WARNING(f'Role not found: {e}'))
        
        self.stdout.write(self.style.SUCCESS('✅ Attendance permissions seeded successfully!'))