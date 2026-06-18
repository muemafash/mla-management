from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.template.loader import render_to_string
from students.models import Fee, Notice, Student
from students.notifications import send_email, send_sms, send_whatsapp
from students import tasks as tasks_module
from django.db.models import F


class Command(BaseCommand):
    help = 'Send reminders (email/SMS/WhatsApp) for upcoming due fees and notices'

    def handle(self, *args, **options):
        days = int(getattr(settings, 'REMINDER_DAYS', 3))
        today = timezone.now().date()
        target = today + timedelta(days=days)

        # Fees due within next `days` or overdue (due_date <= target) and balance > 0
        fees = Fee.objects.filter(due_date__isnull=False, due_date__lte=target).annotate(balance=F('amount') - F('paid')).filter(balance__gt=0)

        self.stdout.write(f'Found {fees.count()} fees to remind')
        for fee in fees:
            student = fee.student
            guardian = student.guardian
            if not guardian:
                continue
            to_email = guardian.email
            # contact fallback: try student.guardian_contact
            phone = student.guardian_contact or getattr(guardian, 'phone_number', None)

            context = {
                'student': student,
                'fee': fee,
                'balance': float(fee.amount) - float(fee.paid),
                'due_in_days': (fee.due_date - today).days if fee.due_date else None,
            }
            subject = render_to_string('emails/fee_reminder_subject.txt', context).strip()
            body = render_to_string('emails/fee_reminder.txt', context)

            # Enqueue the sending via Celery if available
            try:
                tasks_module.send_fee_reminder_task.delay(to_email, phone, subject, body)
                self.stdout.write(f'Enqueued reminder for {to_email} (student {student.admission_no})')
            except Exception:
                # fallback to synchronous
                if send_email(to_email, subject, body):
                    self.stdout.write(f'Email sent to {to_email} for student {student.admission_no}')
                if phone:
                    send_sms(phone, body)
                    send_whatsapp(phone, body)

        # Notices starting within next `days`
        notices = Notice.objects.filter(start_date__isnull=False, start_date__gte=today, start_date__lte=target)
        self.stdout.write(f'Found {notices.count()} upcoming notices')
        for n in notices:
            # determine recipients: if classes attached send to guardians of students in those classes, else send to all guardians
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
                    tasks_module.send_notice_task.delay(to_email, phone, subject, body)
                    self.stdout.write(f'Enqueued notice for {to_email} (student {s.admission_no})')
                except Exception:
                    if send_email(to_email, subject, body):
                        self.stdout.write(f'Notice email sent to {to_email} for student {s.admission_no}')
                    if phone:
                        send_sms(phone, body)
                        send_whatsapp(phone, body)

        self.stdout.write('Reminders finished')
