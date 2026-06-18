from django.contrib import admin
from .models import ClassRoom, Student, Attendance, Fee, Result, Payment, Notice
from .models import Payment
import csv
from django.http import HttpResponse


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'stream')
    filter_horizontal = ('teachers',)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('user', 'admission_no', 'current_class', 'guardian')
    search_fields = ('admission_no', 'user__first_name', 'user__last_name', 'guardian__username')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'present')
    list_filter = ('date', 'present')


@admin.register(Fee)
class FeeAdmin(admin.ModelAdmin):
    list_display = ('student', 'term', 'amount', 'paid')
    search_fields = ('student__admission_no', 'term')
    actions = ['export_fees_csv']

    def export_fees_csv(self, request, queryset):
        meta = self.model._meta
        field_names = ['student', 'admission_no', 'term', 'amount', 'paid', 'due_date']

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=fees.csv'
        writer = csv.writer(response)
        writer.writerow(field_names)
        for obj in queryset.select_related('student'):
            writer.writerow([
                str(obj.student.user.get_full_name()),
                obj.student.admission_no,
                obj.term,
                obj.amount,
                obj.paid,
                obj.due_date,
            ])
        return response

    export_fees_csv.short_description = "Export selected fees to CSV"


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'exam', 'subject', 'score')
    search_fields = ('student__admission_no', 'exam', 'subject')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('fee', 'amount', 'status', 'transaction_id', 'created_at')
    list_filter = ('status',)
    actions = ['export_payments_csv']

    def export_payments_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=payments.csv'
        writer = csv.writer(response)
        writer.writerow(['id', 'student', 'admission_no', 'amount', 'status', 'transaction_id', 'created_at'])
        for p in queryset.select_related('fee__student'):
            writer.writerow([
                p.id,
                p.fee.student.user.get_full_name(),
                p.fee.student.admission_no,
                p.amount,
                p.status,
                p.transaction_id,
                p.created_at,
            ])
        return response

    export_payments_csv.short_description = "Export selected payments to CSV"


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'for_parents', 'start_date', 'end_date', 'created_at')
    filter_horizontal = ('classes',)
    actions = ['send_notice_now']

    def send_notice_now(self, request, queryset):
        from django.template.loader import render_to_string
        from .notifications import send_email, send_sms, send_whatsapp
        count = 0
        for n in queryset:
            if n.classes.exists():
                students = Student.objects.filter(current_class__in=n.classes.all(), guardian__isnull=False).select_related('guardian')
            else:
                students = Student.objects.filter(guardian__isnull=False).select_related('guardian')
            for s in students:
                guardian = s.guardian
                to_email = guardian.email
                phone = s.guardian_contact or getattr(guardian, 'phone_number', None)
                context = {'notice': n, 'student': s}
                subject = render_to_string('emails/notice_subject.txt', context).strip()
                body = render_to_string('emails/notice.txt', context)
                try:
                    from . import tasks as tasks_module
                    tasks_module.send_notice_task.delay(to_email, phone, subject, body)
                    count += 1
                except Exception:
                    if send_email(to_email, subject, body):
                        count += 1
                    if phone:
                        send_sms(phone, body)
                        send_whatsapp(phone, body)
        self.message_user(request, f'Sent notices to {count} recipients')

    send_notice_now.short_description = 'Send selected notices now'
