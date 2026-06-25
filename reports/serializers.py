# reports/serializers.py
from rest_framework import serializers
from .models import Report, ReportSchedule

class ReportSerializer(serializers.ModelSerializer):
    """Report serializer"""
    
    generated_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Report
        fields = [
            'id', 'name', 'report_type', 'format', 'filters',
            'file', 'file_size', 'generated_by', 'generated_by_name',
            'generated_at', 'is_archived', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'generated_at', 'created_at', 'updated_at']
    
    def get_generated_by_name(self, obj):
        return obj.generated_by.get_full_name() if obj.generated_by else None


class ReportScheduleSerializer(serializers.ModelSerializer):
    """Report schedule serializer"""
    
    class Meta:
        model = ReportSchedule
        fields = [
            'id', 'name', 'report_type', 'frequency', 'format',
            'filters', 'recipient_emails', 'is_active',
            'last_run', 'next_run', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'last_run', 'created_at', 'updated_at']


class ReportGenerateSerializer(serializers.Serializer):
    """Serializer for generating reports"""
    
    report_type = serializers.ChoiceField(choices=Report.REPORT_TYPES)
    format = serializers.ChoiceField(choices=[('csv', 'CSV'), ('json', 'JSON')], default='json')
    class_id = serializers.IntegerField(required=False, allow_null=True)
    student_id = serializers.IntegerField(required=False, allow_null=True)
    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)
    term = serializers.CharField(required=False, allow_null=True, allow_blank=True)