from django.urls import path
from . import views

urlpatterns = [
    path('<str:mr_no>/list/', views.followup_list_view, name='followup_list'),
    path('<str:mr_no>/add/', views.followup_form_view, name='followup_add'),
    path('<str:mr_no>/<int:followup_id>/edit/', views.followup_form_view, name='followup_edit'),
    path('<str:mr_no>/<int:followup_id>/delete/', views.followup_delete_view, name='followup_delete'),
]
