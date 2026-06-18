from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_ADMIN = 'admin'
    ROLE_STAFF = 'staff'
    ROLE_TEACHER = 'teacher'
    ROLE_PARENT = 'parent'

    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Administrator'),
        (ROLE_STAFF, 'Staff'),
        (ROLE_TEACHER, 'Teacher'),
        (ROLE_PARENT, 'Parent'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_PARENT)

    def is_admin(self):
        return self.role == self.ROLE_ADMIN or self.is_superuser
