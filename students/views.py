from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
import csv
import json
import requests

from .models import Fee, Payment
from django.db import models
from .models import Student, Result
from .forms import ResultForm
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Notice
from django.utils import timezone
from io import BytesIO


def home(request):
    return render(request, 'students/home.html', {})


def payment_list(request):
    fees = Fee.objects.select_related('student').all()
    payments = Payment.objects.select_related('fee__student').all().order_by('-created_at')
    return render(request, 'students/payments.html', {'fees': fees, 'payments': payments})


def initiate_payment(request, fee_id):
    """Initiate a mobile money payment (MTN or Airtel).

    This creates a pending Payment and returns provider-specific instructions.
    In production this should call the provider's API (USSD/checkout) and return
    the provider's payment URL or mobile instructions.
    """
    fee = get_object_or_404(Fee, id=fee_id)
def mobile_money_webhook(request):
    """Simple webhook endpoint to accept payment notifications from mobile money providers.

    Expected JSON body: {'payment_id': <int>, 'status': 'completed'|'failed', 'transaction_id': <str>}
    This endpoint updates the Payment and Fee records accordingly.
    """
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponseBadRequest('Invalid JSON')

    payment_id = payload.get('payment_id')
    status = payload.get('status')
    txn = payload.get('transaction_id', '')

    if not payment_id or not status:
        return HttpResponseBadRequest('payment_id and status required')

    try:
        payment = Payment.objects.get(id=payment_id)
    except Payment.DoesNotExist:
        return HttpResponse(status=404)

    if status == 'completed':
        payment.transaction_id = txn
        payment.status = Payment.STATUS_COMPLETED
        payment.save()
        fee = payment.fee
        fee.paid = fee.paid + payment.amount
        fee.save()
    elif status == 'failed':
        payment.status = Payment.STATUS_FAILED
        payment.transaction_id = txn
        payment.save()

    return HttpResponse(status=200)


# Backwards-compatibility stub for Stripe webhook URL (removed in favour of mobile money)
@csrf_exempt
def stripe_webhook(request):
    # If Stripe integration is reintroduced, replace this stub with real handling.
    return HttpResponse(status=200)


def _is_teacher(user):
    return user.is_authenticated and getattr(user, 'role', '') == 'teacher'


def teacher_required(view_func):
    decorated = login_required(view_func)
    return user_passes_test(lambda u: _is_teacher(u))(decorated)


def _is_parent(user):
    return user.is_authenticated and getattr(user, 'role', '') == 'parent'


def parent_required(view_func):
    decorated = login_required(view_func)
    return user_passes_test(lambda u: _is_parent(u))(decorated)


@teacher_required
def teacher_dashboard(request):
    user = request.user
    if user.is_superuser:
        students = Student.objects.select_related('user', 'current_class').all()
    else:
        classes = user.classrooms.all()
        students = Student.objects.select_related('user', 'current_class').filter(current_class__in=classes)
    return render(request, 'students/teacher_dashboard.html', {'students': students})


@teacher_required
def add_mark(request):
    if request.method == 'POST':
        form = ResultForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('students:teacher_dashboard')
    else:
        form = ResultForm()
    return render(request, 'students/add_mark.html', {'form': form})


@teacher_required
def student_reportcard(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    results = Result.objects.filter(student=student).order_by('exam', 'subject')

    # Permission: only allow if teacher is assigned to student's class or user is superuser
    user = request.user
    if not (user.is_superuser or (hasattr(user, 'role') and user.role == 'teacher' and student.current_class and user in student.current_class.teachers.all())):
        return HttpResponse('Forbidden', status=403)

    # grouping results by exam
    exams = {}
    for r in results:
        exams.setdefault(r.exam, []).append(r)

    # compute averages
    exam_averages = {exam: (sum([float(x.score) for x in arr]) / len(arr)) if arr else 0 for exam, arr in exams.items()}
    overall_avg = None
    if results:
        overall_avg = sum([float(r.score) for r in results]) / len(results)

    return render(request, 'students/reportcard.html', {
        'student': student,
        'exams': exams,
        'exam_averages': exam_averages,
        'overall_avg': overall_avg,
    })


@parent_required
def parent_dashboard(request):
    user = request.user
    # get children assigned to this parent
    children = getattr(user, 'children', None)
    if children is None:
        children = []
    else:
        children = children.select_related('user', 'current_class').all()

    # notices: ones meant for parents and either global (no classes) or match child's class
    today = timezone.now().date()
    notices = Notice.objects.filter(for_parents=True).filter(
        models.Q(classes__isnull=True) | models.Q(classes__in=[c.current_class for c in children])
    ).distinct()

    # fees for children
    fees = Fee.objects.filter(student__in=children)

    return render(request, 'students/parent_dashboard.html', {
        'children': children,
        'notices': notices,
        'fees': fees,
    })


@teacher_required
def student_reportcard_pdf(request, student_id):
    # Local imports for reportlab to avoid startup errors when not installed
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        from django.contrib.staticfiles import finders
    except Exception:
        return HttpResponse('PDF generation dependencies not installed (reportlab).', status=500)

    student = get_object_or_404(Student, id=student_id)
    results = Result.objects.filter(student=student).order_by('exam', 'subject')

    # Permission check same as HTML view
    user = request.user
    if not (user.is_superuser or (hasattr(user, 'role') and user.role == 'teacher' and student.current_class and user in student.current_class.teachers.all())):
        return HttpResponse('Forbidden', status=403)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elems = []

    elems.append(Paragraph('Mukono Light Academy - Reportcard', styles['Title']))
    elems.append(Spacer(1, 12))
    # Try to include logo if available at static/logo.png
    try:
        logo_path = finders.find('logo.png')
    except Exception:
        logo_path = None
    if logo_path:
        try:
            img = Image(logo_path, width=80, height=80)
            elems.insert(0, img)
        except Exception:
            pass
    elems.append(Paragraph(f'Student: {student.user.get_full_name()}', styles['Normal']))
    elems.append(Paragraph(f'Admission No: {student.admission_no}', styles['Normal']))
    elems.append(Paragraph(f'Class: {student.current_class}', styles['Normal']))
    elems.append(Spacer(1, 12))

    data = [['Exam', 'Subject', 'Score']]
    for r in results:
        data.append([r.exam, r.subject, str(r.score)])

    table = Table(data, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
    ]))
    elems.append(table)
    elems.append(Spacer(1, 12))

    if results:
        overall_avg = sum([float(r.score) for r in results]) / len(results)
        elems.append(Paragraph(f'Overall Average: {overall_avg:.2f}', styles['Normal']))

    doc.build(elems)
    pdf = buffer.getvalue()
    buffer.close()

    resp = HttpResponse(pdf, content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename=reportcard_{student.admission_no}.pdf'
    return resp
