from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create routers for all API endpoints
router = DefaultRouter()
router.register(r'students', views.StudentRegistrationViewSet, basename='student')
router.register(r'timetable', views.TimetableViewSet, basename='timetable')
router.register(r'subjects', views.ClassSubjectViewSet, basename='subjects')
router.register(r'classes', views.ClassRoomViewSet, basename='classes')

urlpatterns = [
    # Existing frontend URLs
    path('', views.home, name='home'),
    path('payments/', views.payment_list, name='payments'),
    path('payments/create/<int:fee_id>/', views.initiate_payment, name='initiate_payment'),
    path('payments/success/', views.payment_success, name='payment_success'),
    path('payments/cancel/', views.payment_cancel, name='payment_cancel'),
    path('export/fees/', views.export_fees_csv, name='export_fees_csv'),
    path('export/payments/', views.export_payments_csv, name='export_payments_csv'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),
    path('webhook/mobile/', views.mobile_money_webhook, name='mobile_money_webhook'),
    path('register/', views.student_register, name='student_register'),
    
    # Teacher area
    path('teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/add-mark/', views.add_mark, name='add_mark'),
    path('teacher/reportcard/<int:student_id>/', views.student_reportcard, name='student_reportcard'),
    path('teacher/reportcard/<int:student_id>/pdf/', views.student_reportcard_pdf, name='student_reportcard_pdf'),
    
    # Parent area
    path('parent/', views.parent_dashboard, name='parent_dashboard'),
    
    # API endpoints - this includes all router URLs
    path('api/', include(router.urls)),
]