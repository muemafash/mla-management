from celery import shared_task
from .notifications import send_email, send_sms, send_whatsapp
from django.template.loader import render_to_string
from django.conf import settings


@shared_task
def send_fee_reminder_task(to_email, phone, subject, body):
    # send email and SMS/WhatsApp (best-effort)
    results = {'email': False, 'sms': False, 'whatsapp': False}
    if to_email:
        results['email'] = send_email(to_email, subject, body)
    if phone:
        results['sms'] = send_sms(phone, body)
        results['whatsapp'] = send_whatsapp(phone, body)
    return results


@shared_task
def send_notice_task(to_email, phone, subject, body):
    results = {'email': False, 'sms': False, 'whatsapp': False}
    if to_email:
        results['email'] = send_email(to_email, subject, body)
    if phone:
        results['sms'] = send_sms(phone, body)
        results['whatsapp'] = send_whatsapp(phone, body)
    return results


@shared_task
def send_reminders_task():
    """Run the management command that enqueues reminders. Intended for Celery Beat."""
    from django.core.management import call_command
    call_command('send_reminders')
    return {'status': 'enqueued'}
