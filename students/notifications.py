import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_email(to_email, subject, message):
    if not to_email:
        logger.warning('No email address provided; skipping email')
        return False
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [to_email], fail_silently=False)
        logger.info('Email sent to %s', to_email)
        return True
    except Exception as e:
        logger.exception('Failed to send email to %s: %s', to_email, e)
        return False


def _twilio_client():
    try:
        from twilio.rest import Client
    except Exception:
        return None
    sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
    token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
    if not sid or not token:
        return None
    return Client(sid, token)


def send_sms(to_number, body):
    client = _twilio_client()
    from_number = getattr(settings, 'TWILIO_FROM_NUMBER', None)
    if not client or not from_number or not to_number:
        logger.warning('Twilio not configured or missing to/from number; skipping SMS')
        return False
    try:
        msg = client.messages.create(body=body, from_=from_number, to=to_number)
        logger.info('SMS sent to %s sid=%s', to_number, getattr(msg, 'sid', None))
        return True
    except Exception as e:
        logger.exception('Failed to send SMS to %s: %s', to_number, e)
        return False


def send_whatsapp(to_number, body):
    client = _twilio_client()
    from_whatsapp = getattr(settings, 'TWILIO_WHATSAPP_FROM', None)
    if not client or not from_whatsapp or not to_number:
        logger.warning('Twilio WhatsApp not configured or missing to/from; skipping WhatsApp')
        return False
    try:
        # Twilio uses 'whatsapp:+123456789'
        to_addr = f'whatsapp:{to_number}'
        msg = client.messages.create(body=body, from_=from_whatsapp, to=to_addr)
        logger.info('WhatsApp sent to %s sid=%s', to_number, getattr(msg, 'sid', None))
        return True
    except Exception as e:
        logger.exception('Failed to send WhatsApp to %s: %s', to_number, e)
        return False
