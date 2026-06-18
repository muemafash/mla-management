from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class UserModelTests(TestCase):
    def test_is_admin_role(self):
        u = User.objects.create_user(username='u1', password='p', role=User.ROLE_ADMIN)
        self.assertTrue(u.is_admin())

    def test_is_admin_superuser(self):
        u = User.objects.create_user(username='u2', password='p', is_superuser=True)
        self.assertTrue(u.is_admin())
