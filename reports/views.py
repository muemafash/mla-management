# reports/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Count  # ADD THIS
from .models import Report, ReportSchedule
from .serializers import (
    ReportSerializer, ReportScheduleSerializer, ReportGenerateSerializer
)
from .services import ReportService
import json

class ReportViewSet(viewsets.ModelViewSet):
    """Report management viewset"""
    
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by report type
        report_type = self.request.query_params.get('report_type')
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        # Filter by user
        if not self.request.user.is_superuser:
            queryset = queryset.filter(generated_by=self.request.user)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(generated_by=self.request.user)
    
    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Generate a report"""
        
        serializer = ReportGenerateSerializer(data=request.data)
        if serializer.is_valid():
            report_type = serializer.validated_data['report_type']
            format_type = serializer.validated_data['format']
            class_id = serializer.validated_data.get('class_id')
            student_id = serializer.validated_data.get('student_id')
            date_from = serializer.validated_data.get('date_from')
            date_to = serializer.validated_data.get('date_to')
            term = serializer.validated_data.get('term')
            
            # Generate report data based on type
            if report_type == 'financial':
                data = ReportService.financial_report(date_from, date_to, class_id)
            elif report_type == 'attendance':
                data = ReportService.attendance_report(class_id, student_id, date_from, date_to)
            elif report_type == 'academic':
                data = ReportService.academic_report(student_id, class_id, term)
            else:
                return Response(
                    {'error': f'Unsupported report type: {report_type}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Export data
            export_data = ReportService.export_report(data, report_type, format_type)
            
            # Save report record
            report = Report.objects.create(
                name=f"{report_type.capitalize()} Report - {timezone.now().strftime('%Y-%m-%d')}",
                report_type=report_type,
                format=format_type,
                filters=serializer.validated_data,
                generated_by=request.user
            )
            
            # Return response
            if format_type == 'csv':
                response = HttpResponse(export_data, content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="{report_type}_report.csv"'
                return response
            else:
                return Response({
                    'message': 'Report generated successfully',
                    'report_id': report.id,
                    'data': data,
                    'export': export_data if format_type == 'json' else None
                })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get report dashboard data"""
        
        # Today's date
        today = timezone.now().date()
        
        # Get counts
        total_reports = Report.objects.count()
        reports_this_month = Report.objects.filter(
            generated_at__month=today.month,
            generated_at__year=today.year
        ).count()
        
        # Recent reports
        recent_reports = Report.objects.all()[:10]
        
        # Report types breakdown
        report_types = Report.objects.values('report_type').annotate(
            count=Count('id')
        )
        
        return Response({
            'total_reports': total_reports,
            'reports_this_month': reports_this_month,
            'recent_reports': ReportSerializer(recent_reports, many=True).data,
            'report_types': list(report_types),
        })

class ReportScheduleViewSet(viewsets.ModelViewSet):
    """Report schedule management viewset"""
    
    queryset = ReportSchedule.objects.all()
    serializer_class = ReportScheduleSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)