from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
import csv
import json
import requests

from .models import Fee, Payment, Student, Result, Notice, Timetable, ClassSubject, ClassRoom
from .forms import ResultForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from io import BytesIO

# REST Framework imports
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.decorators import method_decorator

User = get_user_model()


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
    return render(request, 'students/initiate_payment.html', {'fee': fee})


def payment_success(request):
    """Payment success page"""
    return render(request, 'students/payment_success.html')


def payment_cancel(request):
    """Payment cancelled page"""
    return render(request, 'students/payment_cancel.html')


def mobile_money_webhook(request):
    """Simple webhook endpoint to accept payment notifications from mobile money providers.
    Expected JSON body: {'payment_id': <int>, 'status': 'completed'|'failed', 'transaction_id': <str>}
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


@csrf_exempt
def stripe_webhook(request):
    return HttpResponse(status=200)


def export_fees_csv(request):
    """Export fees as CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="fees.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Student', 'Fee Type', 'Amount Due', 'Paid', 'Balance', 'Status'])
    
    fees = Fee.objects.select_related('student').all()
    for fee in fees:
        writer.writerow([
            fee.student.user.get_full_name(),
            fee.fee_type,
            fee.amount_due,
            fee.paid,
            fee.balance,
            fee.status
        ])
    
    return response


def export_payments_csv(request):
    """Export payments as CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="payments.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Student', 'Fee Type', 'Amount', 'Date', 'Payment Method', 'Status'])
    
    payments = Payment.objects.select_related('fee__student').all()
    for payment in payments:
        writer.writerow([
            payment.fee.student.user.get_full_name(),
            payment.fee.fee_type,
            payment.amount,
            payment.created_at.strftime('%Y-%m-%d'),
            payment.payment_method,
            payment.status
        ])
    
    return response


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

    user = request.user
    if not (user.is_superuser or (hasattr(user, 'role') and user.role == 'teacher' and student.current_class and user in student.current_class.teachers.all())):
        return HttpResponse('Forbidden', status=403)

    exams = {}
    for r in results:
        exams.setdefault(r.exam, []).append(r)

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


@teacher_required
def student_reportcard_pdf(request, student_id):
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

    user = request.user
    if not (user.is_superuser or (hasattr(user, 'role') and user.role == 'teacher' and student.current_class and user in student.current_class.teachers.all())):
        return HttpResponse('Forbidden', status=403)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elems = []

    elems.append(Paragraph('Mukono Light Academy - Reportcard', styles['Title']))
    elems.append(Spacer(1, 12))
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


@parent_required
def parent_dashboard(request):
    user = request.user
    children = getattr(user, 'children', None)
    if children is None:
        children = []
    else:
        children = children.select_related('user', 'current_class').all()

    today = timezone.now().date()
    notices = Notice.objects.filter(for_parents=True).filter(
        models.Q(classes__isnull=True) | models.Q(classes__in=[c.current_class for c in children])
    ).distinct()

    fees = Fee.objects.filter(student__in=children)

    return render(request, 'students/parent_dashboard.html', {
        'children': children,
        'notices': notices,
        'fees': fees,
    })


# ============================================
# STUDENT API - Self Registration & Profile
# ============================================

class StudentRegistrationViewSet(viewsets.ViewSet):
    """
    Student registration and profile management API
    """
    permission_classes = [permissions.AllowAny]
    
    @action(detail=False, methods=['post'])
    @csrf_exempt
    def register(self, request):
        try:
            with transaction.atomic():
                username = request.data.get('username')
                email = request.data.get('email')
                password = request.data.get('password')
                first_name = request.data.get('first_name')
                last_name = request.data.get('last_name')
                date_of_birth = request.data.get('date_of_birth')
                admission_no = request.data.get('admission_no')
                guardian_name = request.data.get('guardian_name', '')
                guardian_contact = request.data.get('guardian_contact', '')
                address = request.data.get('address', '')
                current_class_id = request.data.get('current_class_id')
                
                required_fields = ['username', 'email', 'password', 'first_name', 'last_name', 'admission_no']
                missing_fields = [f for f in required_fields if not request.data.get(f)]
                
                if missing_fields:
                    return Response({
                        'error': f'Missing required fields: {", ".join(missing_fields)}'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if User.objects.filter(username=username).exists():
                    return Response({'error': 'Username already exists'}, status=status.HTTP_400_BAD_REQUEST)
                
                if User.objects.filter(email=email).exists():
                    return Response({'error': 'Email already exists'}, status=status.HTTP_400_BAD_REQUEST)
                
                if Student.objects.filter(admission_no=admission_no).exists():
                    return Response({'error': 'Admission number already exists'}, status=status.HTTP_400_BAD_REQUEST)
                
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )
                
                if address:
                    user.address = address
                user.user_type = 'student'
                user.save()
                
                student = Student.objects.create(
                    user=user,
                    admission_no=admission_no,
                    guardian_name=guardian_name,
                    guardian_contact=guardian_contact,
                    date_of_birth=date_of_birth,
                )
                
                if current_class_id:
                    try:
                        class_obj = ClassRoom.objects.get(id=current_class_id)
                        student.current_class = class_obj
                        student.save()
                    except ClassRoom.DoesNotExist:
                        pass
                
                from users.models import UserRole, Role
                try:
                    student_role = Role.objects.get(name='student')
                    UserRole.objects.create(
                        user=user,
                        role=student_role,
                        assigned_by=None
                    )
                except Role.DoesNotExist:
                    pass
                
                refresh = RefreshToken.for_user(user)
                
                return Response({
                    'message': 'Student registered successfully',
                    'user': {
                        'id': str(user.id),
                        'username': user.username,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'user_type': user.user_type,
                    },
                    'student': {
                        'id': student.id,
                        'admission_no': student.admission_no,
                        'guardian_name': student.guardian_name,
                        'guardian_contact': student.guardian_contact,
                    },
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response({
                'error': f'Registration failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def profile(self, request):
        try:
            student = request.user.student_profile
            return Response({
                'id': student.id,
                'admission_no': student.admission_no,
                'full_name': student.user.get_full_name(),
                'email': student.user.email,
                'username': student.user.username,
                'date_of_birth': student.date_of_birth,
                'guardian_name': student.guardian_name,
                'guardian_contact': student.guardian_contact,
                'current_class': student.current_class.name if student.current_class else None,
                'class_id': student.current_class.id if student.current_class else None,
            })
        except Student.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['put', 'patch'], permission_classes=[permissions.IsAuthenticated])
    def update_profile(self, request):
        try:
            student = request.user.student_profile
            user = request.user
            
            user_fields = ['first_name', 'last_name', 'email', 'address']
            for field in user_fields:
                if field in request.data:
                    setattr(user, field, request.data[field])
            user.save()
            
            student_fields = ['guardian_name', 'guardian_contact', 'date_of_birth']
            for field in student_fields:
                if field in request.data:
                    setattr(student, field, request.data[field])
            
            if 'current_class_id' in request.data:
                try:
                    class_obj = ClassRoom.objects.get(id=request.data['current_class_id'])
                    student.current_class = class_obj
                except ClassRoom.DoesNotExist:
                    pass
            
            student.save()
            
            return Response({
                'message': 'Profile updated successfully',
                'student': {
                    'id': student.id,
                    'admission_no': student.admission_no,
                    'full_name': student.user.get_full_name(),
                    'email': student.user.email,
                    'username': student.user.username,
                    'date_of_birth': student.date_of_birth,
                    'guardian_name': student.guardian_name,
                    'guardian_contact': student.guardian_contact,
                    'current_class': student.current_class.name if student.current_class else None,
                }
            })
            
        except Student.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'Update failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def dashboard(self, request):
        try:
            student = request.user.student_profile
            
            from attendance.models import AttendanceSummary
            try:
                attendance_summary = AttendanceSummary.objects.get(student=student)
                attendance_data = {
                    'total_days': attendance_summary.total_days,
                    'present_days': attendance_summary.present_days,
                    'absent_days': attendance_summary.absent_days,
                    'attendance_percentage': round(attendance_summary.attendance_percentage, 2),
                }
            except AttendanceSummary.DoesNotExist:
                attendance_data = {
                    'total_days': 0,
                    'present_days': 0,
                    'absent_days': 0,
                    'attendance_percentage': 0,
                }
            
            results = Result.objects.filter(student=student)
            if results.exists():
                avg_score = results.aggregate(models.Avg('score'))['score__avg']
                results_data = {
                    'total_subjects': results.values('subject').distinct().count(),
                    'total_exams': results.values('exam').distinct().count(),
                    'average_score': round(avg_score, 2) if avg_score else 0,
                }
            else:
                results_data = {
                    'total_subjects': 0,
                    'total_exams': 0,
                    'average_score': 0,
                }
            
            fees = Fee.objects.filter(student=student)
            total_fees = fees.aggregate(models.Sum('amount'))['amount__sum'] or 0
            total_paid = fees.aggregate(models.Sum('paid'))['paid__sum'] or 0
            
            fees_data = {
                'total_fees': float(total_fees),
                'total_paid': float(total_paid),
                'balance': float(total_fees - total_paid),
                'fees_count': fees.count(),
            }
            
            return Response({
                'student': {
                    'id': student.id,
                    'admission_no': student.admission_no,
                    'name': student.user.get_full_name(),
                    'email': student.user.email,
                    'class': student.current_class.name if student.current_class else None,
                },
                'attendance': attendance_data,
                'academic': results_data,
                'fees': fees_data,
            })
            
        except Student.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=status.HTTP_404_NOT_FOUND)


# ============================================
# TIMETABLE AND CLASS MANAGEMENT API
# ============================================

class TimetableViewSet(viewsets.ModelViewSet):
    """
    Timetable management API
    """
    queryset = Timetable.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        from .serializers import TimetableSerializer
        return TimetableSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        class_id = self.request.query_params.get('class_id')
        if class_id:
            queryset = queryset.filter(class_name_id=class_id)
        
        day = self.request.query_params.get('day')
        if day:
            queryset = queryset.filter(day=day)
        
        teacher_id = self.request.query_params.get('teacher_id')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)
        
        return queryset
    
    @action(detail=False, methods=['post'])
    @csrf_exempt
    def bulk_create(self, request):
        """
        Create multiple timetable entries at once
        POST /api/timetable/bulk_create/
        """
        from .serializers import TimetableBulkSerializer
        
        serializer = TimetableBulkSerializer(data=request.data)
        if serializer.is_valid():
            class_id = serializer.validated_data['class_id']
            entries = serializer.validated_data['entries']
            
            try:
                class_obj = ClassRoom.objects.get(id=class_id)
            except ClassRoom.DoesNotExist:
                return Response(
                    {'error': 'Class not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            created_entries = []
            for entry in entries:
                teacher = None
                if entry.get('teacher_id'):
                    try:
                        teacher = User.objects.get(id=entry['teacher_id'])
                    except User.DoesNotExist:
                        pass
                
                timetable, created = Timetable.objects.update_or_create(
                    class_name=class_obj,
                    day=entry['day'],
                    start_time=entry['start_time'],
                    defaults={
                        'end_time': entry['end_time'],
                        'subject': entry['subject'],
                        'teacher': teacher,
                        'room': entry.get('room', ''),
                        'notes': entry.get('notes', ''),
                    }
                )
                
                # Convert time fields to string safely
                start_time_str = timetable.start_time.strftime('%H:%M') if hasattr(timetable.start_time, 'strftime') else str(timetable.start_time)
                end_time_str = timetable.end_time.strftime('%H:%M') if hasattr(timetable.end_time, 'strftime') else str(timetable.end_time)
                
                created_entries.append({
                    'id': timetable.id,
                    'day': timetable.day,
                    'start_time': start_time_str,
                    'end_time': end_time_str,
                    'subject': timetable.subject,
                })
            
            return Response({
                'message': f'Created/Updated {len(created_entries)} timetable entries',
                'entries': created_entries
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    @csrf_exempt
    def weekly(self, request):
        """
        Get weekly timetable for a class
        GET /api/timetable/weekly/?class_id=1
        """
        from .serializers import TimetableSerializer
        
        class_id = request.query_params.get('class_id')
        if not class_id:
            return Response(
                {'error': 'class_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            class_obj = ClassRoom.objects.get(id=class_id)
        except ClassRoom.DoesNotExist:
            return Response(
                {'error': 'Class not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        entries = Timetable.objects.filter(class_name=class_obj)
        
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
        timetable_data = {}
        
        for day in days:
            day_entries = entries.filter(day=day).order_by('start_time')
            timetable_data[day] = TimetableSerializer(day_entries, many=True).data
        
        return Response({
            'class': class_obj.name,
            'timetable': timetable_data
        })


class ClassSubjectViewSet(viewsets.ModelViewSet):
    """
    Class subjects management API
    """
    queryset = ClassSubject.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        from .serializers import ClassSubjectSerializer
        return ClassSubjectSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        class_id = self.request.query_params.get('class_id')
        if class_id:
            queryset = queryset.filter(class_name_id=class_id)
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset


class ClassRoomViewSet(viewsets.ModelViewSet):
    """
    Classroom management API
    """
    queryset = ClassRoom.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        from .serializers import ClassRoomSerializer
        return ClassRoomSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) |
                models.Q(stream__icontains=search)
            )
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def students(self, request, pk=None):
        """Get students in a class"""
        class_obj = self.get_object()
        students = class_obj.student_set.all().select_related('user')
        
        data = []
        for student in students:
            data.append({
                'id': student.id,
                'admission_no': student.admission_no,
                'name': student.user.get_full_name(),
                'email': student.user.email,
            })
        
        return Response({
            'class': class_obj.name,
            'total_students': len(data),
            'students': data
        })
    
    @action(detail=True, methods=['get'])
    def teachers(self, request, pk=None):
        """Get teachers assigned to a class"""
        class_obj = self.get_object()
        teachers = class_obj.teachers.all()
        
        data = []
        for teacher in teachers:
            data.append({
                'id': teacher.id,
                'username': teacher.username,
                'full_name': teacher.get_full_name(),
                'email': teacher.email,
            })
        
        return Response({
            'class': class_obj.name,
            'total_teachers': len(data),
            'teachers': data
        })


# ============================================
# STANDALONE STUDENT REGISTRATION VIEW
# ============================================

@csrf_exempt
def student_register(request):
    """
    Student self-registration endpoint (standalone view - no CSRF issues)
    POST /students/register/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body.decode('utf-8'))
    except:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    try:
        with transaction.atomic():
            username = data.get('username')
            email = data.get('email')
            password = data.get('password')
            first_name = data.get('first_name')
            last_name = data.get('last_name')
            date_of_birth = data.get('date_of_birth')
            admission_no = data.get('admission_no')
            guardian_name = data.get('guardian_name', '')
            guardian_contact = data.get('guardian_contact', '')
            address = data.get('address', '')
            current_class_id = data.get('current_class_id')
            
            required_fields = ['username', 'email', 'password', 'first_name', 'last_name', 'admission_no']
            missing_fields = [f for f in required_fields if not data.get(f)]
            
            if missing_fields:
                return JsonResponse({
                    'error': f'Missing required fields: {", ".join(missing_fields)}'
                }, status=400)
            
            if User.objects.filter(username=username).exists():
                return JsonResponse({'error': 'Username already exists'}, status=400)
            
            if User.objects.filter(email=email).exists():
                return JsonResponse({'error': 'Email already exists'}, status=400)
            
            if Student.objects.filter(admission_no=admission_no).exists():
                return JsonResponse({'error': 'Admission number already exists'}, status=400)
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            
            if address:
                user.address = address
            user.user_type = 'student'
            user.save()
            
            student = Student.objects.create(
                user=user,
                admission_no=admission_no,
                guardian_name=guardian_name,
                guardian_contact=guardian_contact,
                date_of_birth=date_of_birth,
            )
            
            if current_class_id:
                try:
                    class_obj = ClassRoom.objects.get(id=current_class_id)
                    student.current_class = class_obj
                    student.save()
                except ClassRoom.DoesNotExist:
                    pass
            
            from users.models import UserRole, Role
            try:
                student_role = Role.objects.get(name='student')
                UserRole.objects.create(
                    user=user,
                    role=student_role,
                    assigned_by=None
                )
            except Role.DoesNotExist:
                pass
            
            refresh = RefreshToken.for_user(user)
            
            return JsonResponse({
                'message': 'Student registered successfully',
                'user': {
                    'id': str(user.id),
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'user_type': user.user_type,
                },
                'student': {
                    'id': student.id,
                    'admission_no': student.admission_no,
                    'guardian_name': student.guardian_name,
                    'guardian_contact': student.guardian_contact,
                },
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            }, status=201)
            
    except Exception as e:
        return JsonResponse({'error': f'Registration failed: {str(e)}'}, status=500)