from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from students.models import ClassRoom, Student, Fee

User = get_user_model()


class StudentViewsTests(TestCase):
    def setUp(self):
        self.user_parent = User.objects.create_user(username='parent', password='p', role=User.ROLE_PARENT)
        self.user_teacher = User.objects.create_user(username='teacher', password='p', role=User.ROLE_TEACHER)
        self.user_super = User.objects.create_user(username='super', password='p', is_superuser=True)
        self.classroom = ClassRoom.objects.create(name='P1', stream='A')
        self.classroom.teachers.add(self.user_teacher)
        student_user = User.objects.create_user(username='s1', password='p', first_name='S', last_name='T')
        self.student = Student.objects.create(user=student_user, admission_no='ADM1', current_class=self.classroom, guardian=self.user_parent)
        self.fee = Fee.objects.create(student=self.student, term='T1', amount='100.00', paid='0')

    def test_home(self):
        resp = self.client.get(reverse('students:home'))
        self.assertEqual(resp.status_code, 200)

    def test_export_fees_csv(self):
        resp = self.client.get(reverse('students:export_fees_csv'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('fees_export.csv', resp['Content-Disposition'])
        self.assertIn('admission_no', resp.content.decode())

    def test_teacher_dashboard_requires_login(self):
        resp = self.client.get(reverse('students:teacher_dashboard'))
        self.assertEqual(resp.status_code, 302)

    def test_teacher_dashboard_shows_students(self):
        self.client.force_login(self.user_teacher)
        resp = self.client.get(reverse('students:teacher_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.student.admission_no, resp.content.decode())

    def test_parent_dashboard_shows_children(self):
        self.client.force_login(self.user_parent)
        resp = self.client.get(reverse('students:parent_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.student.admission_no, resp.content.decode())

    def test_reportcard_permission(self):
        other_teacher = User.objects.create_user(username='t2', password='p', role=User.ROLE_TEACHER)
        self.client.force_login(other_teacher)
        url = reverse('students:student_reportcard', args=[self.student.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
        self.client.force_login(self.user_teacher)
        resp2 = self.client.get(url)
        self.assertEqual(resp2.status_code, 200)

    def test_reportcard_pdf(self):
        self.client.force_login(self.user_teacher)
        url = reverse('students:student_reportcard_pdf', args=[self.student.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
