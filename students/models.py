from django.db import models
from django.conf import settings


class ClassRoom(models.Model):
    name = models.CharField(max_length=64)
    stream = models.CharField(max_length=64, blank=True)
    teachers = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='classrooms')

    def __str__(self):
        return f"{self.name}{' - ' + self.stream if self.stream else ''}"


class Student(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_profile')
    admission_no = models.CharField(max_length=32, unique=True)
    date_of_birth = models.DateField(null=True, blank=True)
    guardian_name = models.CharField(max_length=128, blank=True)
    guardian_contact = models.CharField(max_length=32, blank=True)
    current_class = models.ForeignKey(ClassRoom, null=True, blank=True, on_delete=models.SET_NULL)
    guardian = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='children')

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.admission_no})"


class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    date = models.DateField()
    present = models.BooleanField(default=True)
    note = models.TextField(blank=True)

    class Meta:
        unique_together = (('student', 'date'),)


class Fee(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    term = models.CharField(max_length=32)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    due_date = models.DateField(null=True, blank=True)

    def balance(self):
        return self.amount - self.paid


class Result(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    exam = models.CharField(max_length=64)
    subject = models.CharField(max_length=64)
    score = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        unique_together = (('student', 'exam', 'subject'),)


class Notice(models.Model):
    title = models.CharField(max_length=128)
    message = models.TextField()
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    classes = models.ManyToManyField(ClassRoom, blank=True, related_name='notices')
    for_parents = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title}"



class Payment(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    fee = models.ForeignKey(Fee, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.id} - {self.fee.student.admission_no} - {self.amount} ({self.status})"

