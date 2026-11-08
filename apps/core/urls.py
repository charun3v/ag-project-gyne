from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('dashboard/<str:mr_no>/', views.dashboard_view, name='patient_dashboard'),
    path('patients/<str:mr_no>/dashboard/', views.dashboard_view, name='patient_dashboard_alt'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('export/', views.export_data_view, name='export_data'),

    # User Management (Admin)
    path('admin-panel/users/', views.user_list_view, name='user_list'),
    path('admin-panel/users/add/', views.user_form_view, name='user_create'),
    path('admin-panel/users/<int:user_id>/edit/', views.user_form_view, name='user_edit'),
    path('admin-panel/users/<int:user_id>/toggle/', views.user_toggle_active_view, name='user_toggle_active'),

    # Dropdowns & Lookup Tables Manager (Admin)
    path('admin-panel/lookups/', views.lookup_manager_view, name='lookup_manager_default'),
    path('admin-panel/lookups/<str:category>/', views.lookup_manager_view, name='lookup_manager'),
    path('admin-panel/lookups/<str:category>/add/', views.lookup_save_view, name='lookup_add'),
    path('admin-panel/lookups/<str:category>/edit/', views.lookup_save_view, name='lookup_edit_no_id'),
    path('admin-panel/lookups/<str:category>/<int:item_id>/edit/', views.lookup_save_view, name='lookup_edit'),
    path('admin-panel/lookups/<str:category>/<int:item_id>/toggle/', views.lookup_toggle_active_view, name='lookup_toggle_active'),
    path('admin-panel/lookups/<str:category>/<str:item_id>/set-default/', views.lookup_set_default_view, name='lookup_set_default'),
    path('admin-panel/lookups/<str:category>/clear-default/', views.lookup_clear_default_view, name='lookup_clear_default'),
    path('admin-panel/lookups/<str:category>/quick-default/', views.lookup_quick_default_view, name='lookup_quick_default'),

    # Treatment Routing & Formal Approval
    path('treatment/nact/<str:mr_no>/', views.nact_router_view, name='nact_router'),
    path('treatment/ebrt/<str:mr_no>/', views.ebrt_router_view, name='ebrt_router'),
    path('treatment/brachy/<str:mr_no>/', views.brachy_router_view, name='brachy_router'),
    path('treatment/adjuvant/<str:mr_no>/', views.adjuvant_router_view, name='adjuvant_router'),
    path('treatment/approve/<str:course_type>/<int:course_id>/', views.treatment_approve_toggle, name='treatment_approve_toggle'),
]
