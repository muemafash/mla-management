# reports/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone

class Report(models.Model):
    """Report model for storing generated reports"""
    
    REPORT_TYPES = [
        ('financial', 'Financial Report'),
        ('attendance', 'Attendance Report'),
        ('academic', 'Academic Report'),
        ('class', 'Class Report'),
        ('student', 'Student Report'),
        ('fee', 'Fee Report'),
        ('payment', 'Payment Report'),
    ]
    
    FORMATS = [
        ('pdf', 'PDF'),
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON'),
    ]
    
    name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    format = models.CharField(max_length=10, choices=FORMATS, default='pdf')
    
    # Filters used for this report
    filters = models.JSONField(default=dict, blank=True)
    
    # File storage
    file = models.FileField(upload_to='reports/', null=True, blank=True)
    file_size = models.IntegerField(default=0)  # Size in bytes
    
    # Metadata
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_reports'
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    is_archived = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-generated_at']
        verbose_name = 'Report'
        verbose_name_plural = 'Reports'
    
    def __str__(self):
        return f"{self.name} - {self.generated_at.strftime('%Y-%m-%d %H:%M')}"


class ReportSchedule(models.Model):
    """Scheduled report generation"""
    
    FREQUENCIES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
    ]
    
    name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=20, choices=Report.REPORT_TYPES)
    frequency = models.CharField(max_length=20, choices=FREQUENCIES)
    format = models.CharField(max_length=10, choices=Report.FORMATS, default='pdf')
    
    # Filters to apply
    filters = models.JSONField(default=dict, blank=True)
    
    # Recipients
    recipient_emails = models.JSONField(default=list, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Report Schedule'
        verbose_name_plural = 'Report Schedules'
    
    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"