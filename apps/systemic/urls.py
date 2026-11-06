from django.urls import path
from . import views

urlpatterns = [
    path('<str:mr_no>/hub/', views.systemic_hub_view, name='systemic_hub'),
    
    # Concurrent Chemotherapy
    path('<str:mr_no>/concurrent/add/', views.concurrent_form_view, name='concurrent_add'),
    path('<str:mr_no>/concurrent/<int:course_id>/edit/', views.concurrent_form_view, name='concurrent_edit'),
    path('<str:mr_no>/concurrent/<int:course_id>/cycle/add/', views.concurrent_cycle_form_view, name='concurrent_cycle_add'),
    path('<str:mr_no>/concurrent/<int:course_id>/cycle/<int:cycle_id>/edit/', views.concurrent_cycle_form_view, name='concurrent_cycle_edit'),

    # NACT Course & Hierarchical Child Workflows
    path('<str:mr_no>/nact/add/', views.nact_form_view, name='nact_add'),
    path('<str:mr_no>/nact/<int:course_id>/edit/', views.nact_form_view, name='nact_edit'),
    path('<str:mr_no>/nact/<int:course_id>/cycle/add/', views.nact_cycle_add_view, name='nact_cycle_add'),
    path('<str:mr_no>/nact/<int:course_id>/cycle/<int:cycle_id>/edit/', views.nact_cycle_edit_view, name='nact_cycle_edit'),
    path('<str:mr_no>/nact/<int:course_id>/cycle/<int:cycle_id>/delete/', views.nact_cycle_delete_view, name='nact_cycle_delete'),
    path('<str:mr_no>/nact/<int:course_id>/cycle/<int:cycle_id>/copy-previous/', views.nact_copy_previous_cycle_view, name='nact_copy_previous_cycle'),
    path('<str:mr_no>/nact/<int:course_id>/cycle/<int:cycle_id>/drug/add/', views.nact_drug_save_view, name='nact_drug_add'),
    path('<str:mr_no>/nact/<int:course_id>/cycle/<int:cycle_id>/drug/<int:drug_id>/edit/', views.nact_drug_save_view, name='nact_drug_edit'),
    path('<str:mr_no>/nact/<int:course_id>/cycle/<int:cycle_id>/drug/<int:drug_id>/delete/', views.nact_drug_delete_view, name='nact_drug_delete'),

    # Adjuvant Course & Hierarchical Child Workflows
    path('<str:mr_no>/adjuvant/add/', views.adjuvant_form_view, name='adjuvant_add'),
    path('<str:mr_no>/adjuvant/<int:course_id>/edit/', views.adjuvant_form_view, name='adjuvant_edit'),
    path('<str:mr_no>/adjuvant/<int:course_id>/cycle/add/', views.adjuvant_cycle_add_view, name='adjuvant_cycle_add'),
    path('<str:mr_no>/adjuvant/<int:course_id>/cycle/<int:cycle_id>/edit/', views.adjuvant_cycle_edit_view, name='adjuvant_cycle_edit'),
    path('<str:mr_no>/adjuvant/<int:course_id>/cycle/<int:cycle_id>/delete/', views.adjuvant_cycle_delete_view, name='adjuvant_cycle_delete'),
    path('<str:mr_no>/adjuvant/<int:course_id>/cycle/<int:cycle_id>/copy-previous/', views.adjuvant_copy_previous_cycle_view, name='adjuvant_copy_previous_cycle'),
    path('<str:mr_no>/adjuvant/<int:course_id>/cycle/<int:cycle_id>/drug/add/', views.adjuvant_drug_save_view, name='adjuvant_drug_add'),
    path('<str:mr_no>/adjuvant/<int:course_id>/cycle/<int:cycle_id>/drug/<int:drug_id>/edit/', views.adjuvant_drug_save_view, name='adjuvant_drug_edit'),
    path('<str:mr_no>/adjuvant/<int:course_id>/cycle/<int:cycle_id>/drug/<int:drug_id>/delete/', views.adjuvant_drug_delete_view, name='adjuvant_drug_delete'),
]
