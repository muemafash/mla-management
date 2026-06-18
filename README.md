Payment integration (Stripe)

- To enable Stripe Checkout, set environment variables:

```bash
export STRIPE_SECRET_KEY="sk_test_..."  # On Windows use set or PowerShell $env:
export STRIPE_WEBHOOK_SECRET="whsec_..."
```

The app provides endpoints:
	- `/students/payments/` - list fees and payments
	- `/students/payments/create/<fee_id>/` - start a payment (redirects to Stripe)
	- `/students/payments/success/` and `/students/payments/cancel/` - return pages
	- `/students/export/fees/` and `/students/export/payments/` - CSV exports

Branding and printable reportcards

- Place your school logo at `static/logo.png` (PNG recommended). The PDF generator will include it if present.

Frontend styling is in `static/css/reportcard.css`.

Parent area

- Parents should be created as users with role `parent` and then assigned to students via the `guardian` field on the Student model (done in admin).
- Parents can view their children, see outstanding fees and pay via Stripe, and view notices targeted at parents.

Reminders (Email / SMS / WhatsApp)

- Configure environment variables in your environment or deployment settings:

```powershell
set STRIPE_SECRET_KEY=sk_test_...
set STRIPE_WEBHOOK_SECRET=whsec_...
set TWILIO_ACCOUNT_SID=ACxxxx
set TWILIO_AUTH_TOKEN=yyyy
set TWILIO_FROM_NUMBER=+1234567890
set TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
set DEFAULT_FROM_EMAIL=school@yourdomain.org
set REMINDER_DAYS=3
```

- Run reminders manually with the management command:

```powershell
.venv\Scripts\python.exe manage.py send_reminders
```

Reminders will send email via Django's email backend and SMS/WhatsApp via Twilio when configured.

Running with Celery + Redis

- Start a Redis server (example using Docker):

```powershell
docker run -p 6379:6379 -d redis:7
```

- Start a Celery worker from project root:

```powershell
.venv\Scripts\celery -A mukono worker --loglevel=info
```

- Optionally run Celery Beat for scheduled tasks:

```powershell
.venv\Scripts\celery -A mukono beat --loglevel=info
```

The management command `send_reminders` now enqueues sending tasks to Celery; Celery workers will perform deliveries asynchronously.

Celery Beat schedule

- The project includes a Celery Beat schedule that runs `students.tasks.send_reminders_task` weekly on Monday at 09:00 server time. To enable it, run:

```powershell
.venv\Scripts\celery -A mukono beat --loglevel=info
```

Combine Beat with a worker (in separate terminals) so scheduled tasks are executed by workers.


Next steps (suggested):

- Add more apps and REST endpoints (DRF) for integrations.
- Implement front-end views for staff and parents.
- Add permissions, roles and workflows for admissions, attendance and fee payments.
# Mukono Light Academy - Django School Management

This repository contains a minimal Django-based school management system scaffold for Mukono Light Academy.

Getting started:

1. Create a virtual environment and activate it.

```bash
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. Run migrations and create a superuser:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

3. Visit `http://127.0.0.1:8000/` for the site and `http://127.0.0.1:8000/admin/` for admin.

Next steps (suggested):

- Add more apps and REST endpoints (DRF) for integrations.
- Implement front-end views for staff and parents.
- Add permissions, roles and workflows for admissions, attendance and fee payments.
