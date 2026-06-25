# students/serializers.py
from rest_framework import serializers
from .models import Student, ClassRoom, Timetable, ClassSubject, Fee, Payment, Result, Notice

class StudentSerializer(serializers.ModelSerializer):
    """Student serializer with user info"""
    
    full_name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Student
        fields = [
            'id', 'admission_no', 'user', 'full_name', 'email', 'username',
            'date_of_birth', 'guardian_name', 'guardian_contact',
            'current_class', 'class_name'
        ]
        read_only_fields = ['id']
    
    def get_full_name(self, obj):
        return obj.user.get_full_name()
    
    def get_email(self, obj):
        return obj.user.email
    
    def get_username(self, obj):
        return obj.user.username
    
    def get_class_name(self, obj):
        return obj.current_class.name if obj.current_class else None


class TimetableSerializer(serializers.ModelSerializer):
    """Timetable entry serializer"""
    
    class_name_name = serializers.SerializerMethodField()
    teacher_name = serializers.SerializerMethodField()
    day_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Timetable
        fields = [
            'id', 'class_name', 'class_name_name', 'day', 'day_display',
            'start_time', 'end_time', 'subject', 'teacher', 'teacher_name',
            'room', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_class_name_name(self, obj):
        return obj.class_name.name
    
    def get_teacher_name(self, obj):
        return obj.teacher.get_full_name() if obj.teacher else None
    
    def get_day_display(self, obj):
        return obj.get_day_display()


class ClassSubjectSerializer(serializers.ModelSerializer):
    """Class subject serializer"""
    
    class_name_name = serializers.SerializerMethodField()
    teacher_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ClassSubject
        fields = [
            'id', 'class_name', 'class_name_name', 'name', 'code',
            'teacher', 'teacher_name', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_class_name_name(self, obj):
        return obj.class_name.name
    
    def get_teacher_name(self, obj):
        return obj.teacher.get_full_name() if obj.teacher else None


class ClassRoomSerializer(serializers.ModelSerializer):
    """ClassRoom serializer with subjects and timetable"""
    
    subject_count = serializers.SerializerMethodField()
    student_count = serializers.SerializerMethodField()
    teachers = serializers.StringRelatedField(many=True)
    timetable_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ClassRoom
        fields = [
            'id', 'name', 'stream', 'teachers', 'subject_count',
            'student_count', 'timetable_count'
        ]
        read_only_fields = ['id']
    
    def get_subject_count(self, obj):
        return obj.subjects.filter(is_active=True).count()
    
    def get_student_count(self, obj):
        return obj.student_set.count()
    
    def get_timetable_count(self, obj):
        return obj.timetable_entries.count()


class TimetableBulkSerializer(serializers.Serializer):
    """Serializer for bulk timetable creation"""
    
    class_id = serializers.IntegerField()
    entries = serializers.ListField(
        child=serializers.DictField()
    )
    
    def validate_entries(self, value):
        for entry in value:
            required = ['day', 'start_time', 'end_time', 'subject']
            for field in required:
                if field not in entry:
                    raise serializers.ValidationError(f"{field} is required for each entry")
        return value