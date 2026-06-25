# students/management/commands/seed_student_permissions.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from users.models import Role
from students.models import Student

class Command(BaseCommand):
    help = 'Seed student permissions'
    
    def handle(self, *args, **options):
        self.stdout.write('Seeding student permissions...')
        
        try:
            # Get content type for Student model
            content_type = ContentType.objects.get_for_model(Student)
            
            # Define permissions
            permissions_data = [
                ('view_student', 'Can view student'),
                ('add_student', 'Can add student'),
                ('change_student', 'Can change student'),
                ('delete_student', 'Can delete student'),
                ('view_own_student', 'Can view own student profile'),
                ('change_own_student', 'Can change own student profile'),
                ('register_student', 'Can register as student'),
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
                else:
                    self.stdout.write(f'  Permission already exists: {codename}')
            
            # Assign to roles
            try:
                student_role = Role.objects.get(name='student')
                student_role.permissions.add(
                    Permission.objects.get(codename='view_own_student'),
                    Permission.objects.get(codename='change_own_student'),
                )
                self.stdout.write('  Assigned student permissions to Student role')
            except Role.DoesNotExist:
                self.stdout.write('  Student role not found, skipping...')
            
            try:
                admin_role = Role.objects.get(name='admin')
                admin_role.permissions.add(*created_permissions)
                self.stdout.write('  Assigned student permissions to Admin role')
            except Role.DoesNotExist:
                self.stdout.write('  Admin role not found, skipping...')
            
            try:
                teacher_role = Role.objects.get(name='teacher')
                teacher_role.permissions.add(
                    Permission.objects.get(codename='view_student'),
                    Permission.objects.get(codename='add_student'),
                    Permission.objects.get(codename='change_student'),
                )
                self.stdout.write('  Assigned student permissions to Teacher role')
            except Role.DoesNotExist:
                self.stdout.write('  Teacher role not found, skipping...')
            
            self.stdout.write(self.style.SUCCESS('✅ Student permissions seeded successfully!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))
            import traceback
            traceback.print_exc()