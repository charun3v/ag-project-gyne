from django.urls import path
from . import views

urlpatterns = [
    path('<str:mr_no>/hub/', views.radiotherapy_hub_view, name='radiotherapy_hub'),
    path('<str:mr_no>/ebrt/add/', views.ebrt_form_view, name='ebrt_add'),
    path('<str:mr_no>/ebrt/<int:course_id>/edit/', views.ebrt_form_view, name='ebrt_edit'),
    path('<str:mr_no>/ebrt/<int:course_id>/delete/', views.ebrt_course_delete_view, name='ebrt_delete'),
    path('<str:mr_no>/ebrt/<int:course_id>/concurrent-cycle/add/', views.ebrt_concurrent_cycle_save_view, name='ebrt_concurrent_cycle_add'),
    path('<str:mr_no>/ebrt/<int:course_id>/concurrent-cycle/<int:cycle_id>/edit/', views.ebrt_concurrent_cycle_save_view, name='ebrt_concurrent_cycle_edit'),
    path('<str:mr_no>/ebrt/<int:course_id>/concurrent-cycle/<int:cycle_id>/delete/', views.ebrt_concurrent_cycle_delete_view, name='ebrt_concurrent_cycle_delete'),
    path('<str:mr_no>/brachy/add/', views.brachy_form_view, name='brachy_add'),
    path('<str:mr_no>/brachy/<int:course_id>/edit/', views.brachy_form_view, name='brachy_edit'),
    path('<str:mr_no>/brachy/<int:course_id>/delete/', views.brachy_course_delete_view, name='brachy_delete'),
    path('<str:mr_no>/brachy/<int:course_id>/session/add/', views.brachy_session_form_view, name='brachy_session_add'),
    path('<str:mr_no>/brachy/<int:course_id>/session/<int:session_id>/edit/', views.brachy_session_form_view, name='brachy_session_edit'),
    path('<str:mr_no>/brachy/<int:course_id>/session/<int:session_id>/delete/', views.brachy_session_delete_view, name='brachy_session_delete'),
    path('<str:mr_no>/brachy/<int:course_id>/session/<int:session_id>/application/add/', views.brachy_application_save_view, name='brachy_application_add'),
    path('<str:mr_no>/brachy/<int:course_id>/session/<int:session_id>/application/<int:fraction_id>/edit/', views.brachy_application_save_view, name='brachy_application_edit'),
    path('<str:mr_no>/brachy/<int:course_id>/session/<int:session_id>/application/<int:fraction_id>/delete/', views.brachy_application_delete_view, name='brachy_application_delete'),
    
    # Applicator rules API and configuration
    path('api/applicator-rules/', views.api_applicator_rules_view, name='api_applicator_rules_all'),
    path('api/applicator-rules/<int:applicator_id>/', views.api_applicator_rules_view, name='api_applicator_rules'),
    path('admin/applicator-rules/', views.applicator_rules_admin_view, name='applicator_rules_admin'),
]
