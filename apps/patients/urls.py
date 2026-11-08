from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.patient_register_view, name='patient_register'),
    path('<str:mr_no>/edit/', views.patient_edit_view, name='patient_edit'),
    path('search/', views.patient_search_view, name='patient_search'),
    path('<str:mr_no>/dashboard/', views.patient_dashboard_view, name='patient_dashboard_direct'),
    path('<str:mr_no>/summary/', views.patient_summary_view, name='patient_summary'),
    path('<str:mr_no>/summary/pdf/', views.patient_summary_pdf_view, name='patient_summary_pdf'),
    path('<str:mr_no>/delete/', views.patient_delete_view, name='patient_delete'),
]
