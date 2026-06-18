from django.test import TestCase
from django.contrib.auth import get_user_model

from students.models import ClassRoom, Student, Fee, Payment
from decimal import Decimal

User = get_user_model()


class StudentModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='s1', password='pass', first_name='First', last_name='Last')
        self.classroom = ClassRoom.objects.create(name='P1', stream='A')
        self.student = Student.objects.create(user=self.user, admission_no='ADM001', current_class=self.classroom)

    def test_str(self):
        self.assertIn('ADM001', str(self.student))

    def test_fee_balance(self):
        fee = Fee.objects.create(student=self.student, term='Term1', amount=Decimal('1000.00'), paid=Decimal('200.00'))
        self.assertEqual(fee.balance(), fee.amount - fee.paid)

    def test_payment_str(self):
        fee = Fee.objects.create(student=self.student, term='Term1', amount=Decimal('100.00'), paid=Decimal('0'))
        payment = Payment.objects.create(fee=fee, amount=Decimal('50.00'), status=Payment.STATUS_PENDING)
        self.assertIn(str(payment.amount), str(payment))
