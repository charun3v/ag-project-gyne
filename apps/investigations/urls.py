from django.urls import path
from . import views

urlpatterns = [
    path('<str:mr_no>/hub/', views.investigations_hub_view, name='investigations_hub'),
    path('<str:mr_no>/pdf/', views.investigations_pdf_view, name='investigations_pdf'),
    path('<str:mr_no>/blood/add/', views.blood_form_view, name='blood_add'),
    path('<str:mr_no>/blood/<int:blood_id>/edit/', views.blood_form_view, name='blood_edit'),
    path('<str:mr_no>/pathology/add/', views.pathology_form_view, name='pathology_add'),
    path('<str:mr_no>/pathology/<int:path_id>/edit/', views.pathology_form_view, name='pathology_edit'),
    path('<str:mr_no>/imaging/add/', views.imaging_form_view, name='imaging_add'),
    path('<str:mr_no>/imaging/<int:imaging_id>/edit/', views.imaging_form_view, name='imaging_edit'),
    path('<str:mr_no>/molecular/add/', views.molecular_form_view, name='molecular_add'),
    path('<str:mr_no>/molecular/<int:molecular_id>/edit/', views.molecular_form_view, name='molecular_edit'),
]
