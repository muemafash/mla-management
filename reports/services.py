# reports/services.py
from django.db.models import Sum, Count, Avg, Max, Min, Q
from django.utils import timezone
from datetime import datetime, timedelta
from students.models import Student, ClassRoom, Fee, Payment
from attendance.models import Attendance, AttendanceSummary
from accounts.models import User
import csv
from io import StringIO, BytesIO
import json

class ReportService:
    """Service class for generating various reports"""
    
    @staticmethod
    def financial_report(start_date=None, end_date=None, class_id=None):
        """Generate financial report"""
        
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        # Get payments
        payments = Payment.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        if class_id:
            payments = payments.filter(fee__student__current_class_id=class_id)
        
        # Calculate totals
        total_collected = payments.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
        total_pending = payments.filter(status='pending').aggregate(Sum('amount'))['amount__sum'] or 0
        total_failed = payments.filter(status='failed').aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Fee summary
        fees = Fee.objects.all()
        if class_id:
            fees = fees.filter(student__current_class_id=class_id)
        
        total_fees = fees.aggregate(Sum('amount'))['amount__sum'] or 0
        total_paid = fees.aggregate(Sum('paid'))['paid__sum'] or 0
        total_balance = total_fees - total_paid
        
        # By payment type
        by_type = payments.values('fee__student__current_class__name').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        return {
            'period': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d')
            },
            'summary': {
                'total_collected': float(total_collected),
                'total_pending': float(total_pending),
                'total_failed': float(total_failed),
                'total_fees': float(total_fees),
                'total_paid': float(total_paid),
                'total_balance': float(total_balance),
            },
            'by_class': list(by_type),
            'transactions': list(payments.values('id', 'amount', 'status', 'created_at')[:100])
        }
    
    @staticmethod
    def attendance_report(class_id=None, student_id=None, date_from=None, date_to=None):
        """Generate attendance report"""
        
        if not date_from:
            date_from = timezone.now() - timedelta(days=30)
        if not date_to:
            date_to = timezone.now()
        
        # Get attendance records
        attendance_qs = Attendance.objects.filter(
            date__range=[date_from, date_to]
        )
        
        if class_id:
            attendance_qs = attendance_qs.filter(student__current_class_id=class_id)
        if student_id:
            attendance_qs = attendance_qs.filter(student_id=student_id)
        
        # Get summary
        summary_qs = AttendanceSummary.objects.all()
        if class_id:
            summary_qs = summary_qs.filter(student__current_class_id=class_id)
        if student_id:
            summary_qs = summary_qs.filter(student_id=student_id)
        
        total_days = attendance_qs.values('date').distinct().count()
        present = attendance_qs.filter(present=True).count()
        absent = attendance_qs.filter(present=False).count()
        
        # By class
        by_class = attendance_qs.values('student__current_class__name').annotate(
            present_count=Count('id', filter=Q(present=True)),
            total_count=Count('id')
        )
        
        return {
            'period': {
                'from': date_from.strftime('%Y-%m-%d'),
                'to': date_to.strftime('%Y-%m-%d')
            },
            'summary': {
                'total_days': total_days,
                'present': present,
                'absent': absent,
                'attendance_rate': round((present / (present + absent) * 100) if (present + absent) > 0 else 0, 2)
            },
            'by_class': list(by_class),
            'student_summaries': list(summary_qs.values(
                'student__user__first_name',
                'student__user__last_name',
                'student__admission_no',
                'total_days',
                'present_days',
                'absent_days',
                'attendance_percentage'
            )[:50])
        }
    
    @staticmethod
    def academic_report(student_id=None, class_id=None, term=None):
        """Generate academic report"""
        
        from students.models import Result
        
        results = Result.objects.all()
        
        if student_id:
            results = results.filter(student_id=student_id)
        if class_id:
            results = results.filter(student__current_class_id=class_id)
        if term:
            results = results.filter(exam__icontains=term)
        
        # Overall statistics
        total_students = results.values('student').distinct().count()
        total_subjects = results.values('subject').distinct().count()
        avg_score = results.aggregate(Avg('score'))['score__avg'] or 0
        
        # By subject
        by_subject = results.values('subject').annotate(
            avg_score=Avg('score'),
            max_score=Max('score'),
            min_score=Min('score'),
            total_students=Count('student', distinct=True)
        )
        
        # Top performers
        top_students = results.values(
            'student__user__first_name',
            'student__user__last_name',
            'student__admission_no'
        ).annotate(
            avg_score=Avg('score')
        ).order_by('-avg_score')[:10]
        
        return {
            'overview': {
                'total_students': total_students,
                'total_subjects': total_subjects,
                'average_score': round(float(avg_score), 2)
            },
            'by_subject': list(by_subject),
            'top_students': list(top_students)
        }
    
    @staticmethod
    def export_report(data, report_type, format='csv'):
        """Export report data to various formats"""
        
        if format == 'csv':
            return ReportService._export_csv(data, report_type)
        elif format == 'json':
            return ReportService._export_json(data)
        else:
            return None
    
    @staticmethod
    def _export_csv(data, report_type):
        """Export data to CSV format"""
        
        output = StringIO()
        
        if report_type == 'financial':
            writer = csv.writer(output)
            writer.writerow(['Metric', 'Value'])
            for key, value in data.get('summary', {}).items():
                writer.writerow([key.replace('_', ' ').title(), value])
        
        elif report_type == 'attendance':
            writer = csv.writer(output)
            writer.writerow(['Student', 'Admission No', 'Total Days', 'Present', 'Absent', 'Percentage'])
            for student in data.get('student_summaries', []):
                writer.writerow([
                    f"{student.get('student__user__first_name', '')} {student.get('student__user__last_name', '')}",
                    student.get('student__admission_no', ''),
                    student.get('total_days', 0),
                    student.get('present_days', 0),
                    student.get('absent_days', 0),
                    student.get('attendance_percentage', 0)
                ])
        
        elif report_type == 'academic':
            writer = csv.writer(output)
            writer.writerow(['Subject', 'Average Score', 'Max Score', 'Min Score', 'Students'])
            for subject in data.get('by_subject', []):
                writer.writerow([
                    subject.get('subject', ''),
                    round(subject.get('avg_score', 0), 2),
                    subject.get('max_score', 0),
                    subject.get('min_score', 0),
                    subject.get('total_students', 0)
                ])
        
        return output.getvalue()
    
    @staticmethod
    def _export_json(data):
        """Export data to JSON format"""
        return json.dumps(data, indent=2, default=str)