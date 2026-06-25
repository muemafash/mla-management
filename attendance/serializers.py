# attendance/serializers.py
from rest_framework import serializers
from .models import Attendance, ClassAttendance, AttendanceSummary
from students.models import Student

class AttendanceSerializer(serializers.ModelSerializer):
    """Attendance record serializer"""
    
    student_name = serializers.SerializerMethodField()
    student_class = serializers.SerializerMethodField()
    recorded_by_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()  # Convert boolean to string
    
    class Meta:
        model = Attendance
        fields = [
            'id', 'student', 'student_name', 'student_class',
            'date', 'present', 'status', 'recorded_by', 'recorded_by_name',
            'note', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_student_name(self, obj):
        return obj.student.user.get_full_name()
    
    def get_student_class(self, obj):
        return obj.student.current_class.name if obj.student.current_class else None
    
    def get_recorded_by_name(self, obj):
        return obj.recorded_by.get_full_name() if obj.recorded_by else None
    
    def get_status(self, obj):
        return 'present' if obj.present else 'absent'


class BulkAttendanceSerializer(serializers.Serializer):
    """Serializer for bulk attendance recording"""
    
    class_id = serializers.IntegerField()
    date = serializers.DateField()
    records = serializers.ListField(
        child=serializers.DictField()
    )
    
    def validate_records(self, value):
        for record in value:
            if 'student_id' not in record:
                raise serializers.ValidationError("Each record must have student_id")
            if 'status' not in record:
                raise serializers.ValidationError("Each record must have status")
            if record['status'] not in ['present', 'absent']:
                raise serializers.ValidationError(f"Invalid status: {record['status']}")
        return value


class ClassAttendanceSerializer(serializers.ModelSerializer):
    """Class attendance serializer"""
    
    class_name = serializers.StringRelatedField()
    recorded_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ClassAttendance
        fields = [
            'id', 'class_name', 'date', 'recorded_by',
            'recorded_by_name', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_recorded_by_name(self, obj):
        return obj.recorded_by.get_full_name() if obj.recorded_by else None


class AttendanceSummarySerializer(serializers.ModelSerializer):
    """Attendance summary serializer"""
    
    student_name = serializers.SerializerMethodField()
    student_class = serializers.SerializerMethodField()
    
    class Meta:
        model = AttendanceSummary
        fields = [
            'id', 'student', 'student_name', 'student_class',
            'total_days', 'present_days', 'absent_days',
            'attendance_percentage', 'updated_at'
        ]
        read_only_fields = ['id', 'updated_at']
    
    def get_student_name(self, obj):
        return obj.student.user.get_full_name()
    
    def get_student_class(self, obj):
        return obj.student.current_class.name if obj.student.current_class else None