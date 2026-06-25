# attendance/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.shortcuts import get_object_or_404
from .models import Attendance, ClassAttendance, AttendanceSummary
from .serializers import (
    AttendanceSerializer, BulkAttendanceSerializer,
    ClassAttendanceSerializer, AttendanceSummarySerializer
)
from students.models import Student, ClassRoom
from datetime import datetime, timedelta

class AttendanceViewSet(viewsets.ModelViewSet):
    """Attendance management viewset"""
    
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        user = self.request.user
        queryset = Attendance.objects.all()
        
        # Filter by student
        student_id = self.request.query_params.get('student_id')
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        
        # Filter by class
        class_id = self.request.query_params.get('class_id')
        if class_id:
            queryset = queryset.filter(student__current_class_id=class_id)
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        # Filter by status (using present field from your model)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            if status_filter == 'present':
                queryset = queryset.filter(present=True)
            elif status_filter == 'absent':
                queryset = queryset.filter(present=False)
        
        # If user is a student, only show their own attendance
        if hasattr(user, 'student_profile'):
            queryset = queryset.filter(student=user.student_profile)
        
        # If user is a parent, only show their children's attendance
        if hasattr(user, 'children'):
            child_ids = user.children.values_list('id', flat=True)
            queryset = queryset.filter(student_id__in=child_ids)
        
        return queryset
    
    @action(detail=False, methods=['post'])
    def bulk_record(self, request):
        """Record attendance for multiple students at once"""
        
        # Check if user is a teacher or admin
        if not (request.user.is_superuser or 
                hasattr(request.user, 'role') and request.user.role == 'teacher'):
            return Response(
                {'error': 'Only teachers can record attendance'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = BulkAttendanceSerializer(data=request.data)
        if serializer.is_valid():
            class_id = serializer.validated_data['class_id']
            date = serializer.validated_data['date']
            records = serializer.validated_data['records']
            
            # Get the class
            try:
                class_obj = ClassRoom.objects.get(id=class_id)
            except ClassRoom.DoesNotExist:
                return Response(
                    {'error': 'Class not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Create or update attendance records
            created_records = []
            for record in records:
                student_id = record['student_id']
                status_value = record['status']
                notes = record.get('notes', '')
                
                # Convert status to boolean (present=True, absent=False)
                is_present = status_value == 'present'
                
                # Verify student belongs to this class
                try:
                    student = Student.objects.get(id=student_id, current_class=class_obj)
                except Student.DoesNotExist:
                    continue
                
                # Create or update attendance using your model's fields
                attendance, created = Attendance.objects.update_or_create(
                    student=student,
                    date=date,
                    defaults={
                        'present': is_present,
                        'note': notes
                    }
                )
                
                # Update summary
                summary, _ = AttendanceSummary.objects.get_or_create(student=student)
                summary.update_summary()
                
                created_records.append({
                    'student_id': student.id,
                    'student_name': student.user.get_full_name(),
                    'status': status_value,
                    'created': created
                })
            
            # Create class attendance record
            class_attendance, _ = ClassAttendance.objects.update_or_create(
                class_name=class_obj,
                date=date,
                defaults={
                    'recorded_by': request.user,
                    'notes': request.data.get('notes', '')
                }
            )
            
            return Response({
                'message': f'Attendance recorded for {len(created_records)} students',
                'records': created_records,
                'class': class_obj.name,
                'date': date
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get attendance summary"""
        
        # If student_id is provided, get summary for that student
        student_id = request.query_params.get('student_id')
        
        # If user is a student, get their summary
        if hasattr(request.user, 'student_profile'):
            student_id = request.user.student_profile.id
        
        # If user is a parent, get summary for all children
        if hasattr(request.user, 'children'):
            child_ids = request.user.children.values_list('id', flat=True)
            summaries = AttendanceSummary.objects.filter(student_id__in=child_ids)
            serializer = AttendanceSummarySerializer(summaries, many=True)
            return Response(serializer.data)
        
        # If student_id is provided, get summary for that student
        if student_id:
            try:
                summary = AttendanceSummary.objects.get(student_id=student_id)
                serializer = AttendanceSummarySerializer(summary)
                return Response(serializer.data)
            except AttendanceSummary.DoesNotExist:
                return Response({'error': 'Summary not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Admin can see all summaries
        if request.user.is_superuser:
            summaries = AttendanceSummary.objects.all()
            serializer = AttendanceSummarySerializer(summaries, many=True)
            return Response(serializer.data)
        
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    @action(detail=False, methods=['get'])
    def class_report(self, request):
        """Get attendance report for a class"""
        
        class_id = request.query_params.get('class_id')
        if not class_id:
            return Response(
                {'error': 'class_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        date_from = request.query_params.get('date_from', '')
        date_to = request.query_params.get('date_to', '')
        
        # Get the class
        try:
            class_obj = ClassRoom.objects.get(id=class_id)
        except ClassRoom.DoesNotExist:
            return Response(
                {'error': 'Class not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get students in class
        students = Student.objects.filter(current_class=class_obj)
        
        # Build attendance data
        attendance_data = []
        for student in students:
            # Get attendance for this student using the correct related name
            attendances = student.attendance_records.all()  # FIXED: changed from attendance_set to attendance_records
            if date_from:
                attendances = attendances.filter(date__gte=date_from)
            if date_to:
                attendances = attendances.filter(date__lte=date_to)
            
            total = attendances.count()
            present = attendances.filter(present=True).count()
            absent = attendances.filter(present=False).count()
            
            if total > 0:
                percentage = (present / total) * 100
            else:
                percentage = 0
            
            attendance_data.append({
                'student_id': student.id,
                'student_name': student.user.get_full_name(),
                'admission_no': student.admission_no,
                'total_days': total,
                'present': present,
                'absent': absent,
                'percentage': round(percentage, 2),
            })
        
        return Response({
            'class': class_obj.name,
            'total_students': len(attendance_data),
            'date_range': {
                'from': date_from or 'All',
                'to': date_to or 'All'
            },
            'data': attendance_data
        })
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """Get today's attendance for a class or student"""
        
        today = timezone.now().date()
        class_id = request.query_params.get('class_id')
        
        if class_id:
            # Get attendance for today for a class
            try:
                class_obj = ClassRoom.objects.get(id=class_id)
            except ClassRoom.DoesNotExist:
                return Response(
                    {'error': 'Class not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            students = Student.objects.filter(current_class=class_obj)
            attendance_data = []
            
            for student in students:
                attendance = Attendance.objects.filter(
                    student=student,
                    date=today
                ).first()
                
                attendance_data.append({
                    'student_id': student.id,
                    'student_name': student.user.get_full_name(),
                    'status': 'present' if attendance and attendance.present else 'absent' if attendance else 'not_recorded',
                    'notes': attendance.note if attendance else '',
                })
            
            return Response({
                'class': class_obj.name,
                'date': today,
                'total_students': len(attendance_data),
                'records': attendance_data
            })
        
        # If user is a student, get their today's attendance
        if hasattr(request.user, 'student_profile'):
            student = request.user.student_profile
            attendance = Attendance.objects.filter(
                student=student,
                date=today
            ).first()
            
            return Response({
                'student': student.user.get_full_name(),
                'date': today,
                'status': 'present' if attendance and attendance.present else 'absent' if attendance else 'not_recorded',
                'notes': attendance.note if attendance else '',
            })
        
        return Response(
            {'error': 'class_id required or not a student'},
            status=status.HTTP_400_BAD_REQUEST
        )