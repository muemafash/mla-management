# reports/admin.py
from django.contrib import admin
from .models import Report, ReportSchedule

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('name', 'report_type', 'format', 'generated_by', 'generated_at', 'is_archived')
    list_filter = ('report_type', 'format', 'is_archived', 'generated_at')
    search_fields = ('name', 'generated_by__username')
    readonly_fields = ('generated_at', 'created_at', 'updated_at', 'file_size')
    date_hierarchy = 'generated_at'

@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'report_type', 'frequency', 'is_active', 'last_run', 'next_run')
    list_filter = ('report_type', 'frequency', 'is_active')
    search_fields = ('name',)
    readonly_fields = ('last_run', 'created_at', 'updated_at')