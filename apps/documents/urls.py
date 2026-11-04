from django.urls import path
from . import views

urlpatterns = [
    path('<str:mr_no>/', views.document_list_view, name='document_list'),
    path('view/<int:doc_id>/', views.download_document_view, name='download_document'),
    path('delete/<int:doc_id>/', views.delete_document_view, name='delete_document'),
]
