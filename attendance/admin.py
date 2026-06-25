# attendance/admin.py
from django.contrib import admin
from .models import Attendance, ClassAttendance, AttendanceSummary

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'present', 'recorded_by')  # Changed: status -> present
    list_filter = ('present', 'date', 'recorded_by')  # Changed: status -> present
    search_fields = ('student__user__first_name', 'student__user__last_name')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'date'

@admin.register(ClassAttendance)
class ClassAttendanceAdmin(admin.ModelAdmin):
    list_display = ('class_name', 'date', 'recorded_by')
    list_filter = ('date', 'class_name')
    search_fields = ('class_name__name',)
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'date'

@admin.register(AttendanceSummary)
class AttendanceSummaryAdmin(admin.ModelAdmin):
    list_display = ('student', 'attendance_percentage', 'total_days', 'updated_at')
    list_filter = ('attendance_percentage',)
    search_fields = ('student__user__first_name', 'student__user__last_name')
    readonly_fields = ('updated_at',)