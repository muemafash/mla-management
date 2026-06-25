# attendance/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone

class Attendance(models.Model):
    """Attendance record for a student on a specific date"""
    
    # Using your existing Attendance model structure
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='attendance_records'  # Changed to avoid conflict with your existing related_name
    )
    
    date = models.DateField(default=timezone.now)
    present = models.BooleanField(default=True)  # Your existing field
    note = models.TextField(blank=True)  # Your existing field
    
    # Additional fields
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_attendances'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'date']
        ordering = ['-date', 'student__user__first_name']
        verbose_name = 'Attendance'
        verbose_name_plural = 'Attendance Records'
    
    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.date} - {'Present' if self.present else 'Absent'}"


class ClassAttendance(models.Model):
    """Bulk attendance for a class on a specific date"""
    
    class_name = models.ForeignKey(
        'students.ClassRoom',  # FIXED: Changed from 'students.Class' to 'students.ClassRoom'
        on_delete=models.CASCADE,
        related_name='class_attendances'
    )
    
    date = models.DateField(default=timezone.now)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='class_attendance_records'
    )
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['class_name', 'date']
        ordering = ['-date', 'class_name__name']  # FIXED: class_name__name works with ClassRoom
        verbose_name = 'Class Attendance'
        verbose_name_plural = 'Class Attendance Records'
    
    def __str__(self):
        return f"{self.class_name.name} - {self.date}"


class AttendanceSummary(models.Model):
    """Summary of attendance for a student over time"""
    
    student = models.OneToOneField(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='attendance_summary'
    )
    
    total_days = models.IntegerField(default=0)
    present_days = models.IntegerField(default=0)
    absent_days = models.IntegerField(default=0)
    
    attendance_percentage = models.FloatField(default=0.0)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Attendance Summary'
        verbose_name_plural = 'Attendance Summaries'
    
    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.attendance_percentage}%"
    
    def update_summary(self):
        """Update attendance summary from attendance records"""
        attendances = self.student.attendance_records.all()  # Using new related_name
        
        self.total_days = attendances.count()
        self.present_days = attendances.filter(present=True).count()
        self.absent_days = attendances.filter(present=False).count()
        
        if self.total_days > 0:
            self.attendance_percentage = (self.present_days / self.total_days) * 100
        else:
            self.attendance_percentage = 0.0
        
        self.save()