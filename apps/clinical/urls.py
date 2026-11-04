from django.urls import path
from . import views

urlpatterns = [
    path('<str:mr_no>/history/', views.history_detail_view, name='history_detail'),
    path('<str:mr_no>/diagnosis/', views.diagnosis_detail_view, name='diagnosis_detail'),
    path('<str:mr_no>/diagnosis/<int:diagnosis_id>/', views.diagnosis_detail_view, name='diagnosis_edit'),
    path('<str:mr_no>/diagnosis/delete/<int:diagnosis_id>/', views.diagnosis_delete_view, name='diagnosis_delete'),
    path('<str:mr_no>/diagnosis/set-primary/<int:diagnosis_id>/', views.diagnosis_set_primary_view, name='diagnosis_set_primary'),
    path('<str:mr_no>/examination/pdf/', views.examination_pdf_view, {'enc_type': 'baseline'}, name='examination_pdf_default'),
    path('<str:mr_no>/examination/<path:enc_type>/pdf/', views.examination_pdf_view, name='examination_pdf'),
    path('<str:mr_no>/examination/', views.examination_detail_view, {'enc_type': 'baseline'}, name='examination_detail_default'),
    path('<str:mr_no>/examination/<path:enc_type>/', views.examination_detail_view, name='examination_detail'),
    path('encounter/<int:encounter_id>/diagram/', views.ibs_diagram_view, name='ibs_diagram'),
    path('encounter/<int:encounter_id>/diagram/save/', views.save_diagram_findings_view, name='save_diagram_findings'),
    path('encounter/<int:encounter_id>/auto-populate-svg/', views.auto_populate_svg_view, name='auto_populate_svg'),
    path('encounter/<int:encounter_id>/auto-populate-previous/', views.auto_populate_previous_diagram_view, name='auto_populate_previous_diagram'),
]
