import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponseForbidden

from patients.models import Patient
from core.models import AuditLog
from documents.models import PatientDocument

@login_required
def document_list_view(request, mr_no):
    """
    Replicates private document & multimedia management for the patient.
    Allows uploading and viewing clinical photos, scans, videos, and PDFs.
    """
    patient = get_object_or_404(Patient, mr_no=mr_no)
    documents = patient.documents.all().order_by('-uploaded_on')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        category = request.POST.get('category', 'clinical_photo')
        notes = request.POST.get('notes', '').strip()
        uploaded_file = request.FILES.get('document_file')

        if not uploaded_file:
            messages.error(request, "Please select a file to upload.")
            return redirect('document_list', mr_no=patient.mr_no)

        if not title:
            title = uploaded_file.name

        doc = PatientDocument.objects.create(
            patient=patient,
            category=category,
            title=title,
            file=uploaded_file,
            file_type=uploaded_file.content_type,
            file_size_bytes=uploaded_file.size,
            uploaded_by=request.user,
            notes=notes,
            is_confidential=True
        )

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="INSERT",
            table_affected="tblPatientDocuments",
            record_ref=f"{patient.mr_no}-Doc#{doc.document_id}",
            notes=f"Uploaded {doc.get_category_display()}: {doc.title} ({doc.file_size_formatted})"
        )

        messages.success(request, f"File '{doc.title}' uploaded successfully.")
        return redirect('document_list', mr_no=patient.mr_no)

    return render(request, 'documents/document_list.html', {
        'patient': patient,
        'documents': documents,
        'category_choices': PatientDocument.CATEGORY_CHOICES,
    })


@login_required
def download_document_view(request, doc_id):
    """Secure, authenticated media streaming for private patient uploads."""
    doc = get_object_or_404(PatientDocument, document_id=doc_id)

    if not doc.file or not os.path.exists(doc.file.path):
        raise Http404("Document file does not exist on storage server.")

    # Audit file access
    AuditLog.objects.create(
        username=request.user.username,
        full_name=request.user.first_name,
        action="ACCESS",
        table_affected="tblPatientDocuments",
        record_ref=f"Doc#{doc.document_id}",
        notes=f"Downloaded/viewed {doc.title}"
    )

    response = FileResponse(open(doc.file.path, 'rb'), content_type=doc.file_type or 'application/octet-stream')
    response['Content-Disposition'] = f'inline; filename="{os.path.basename(doc.file.name)}"'
    return response


@login_required
def delete_document_view(request, doc_id):
    """Secure deletion of uploaded document."""
    doc = get_object_or_404(PatientDocument, document_id=doc_id)
    mr_no = doc.patient.mr_no
    title = doc.title

    if request.method == 'POST':
        # Remove physical file if exists
        if doc.file and os.path.exists(doc.file.path):
            try:
                os.remove(doc.file.path)
            except Exception:
                pass

        doc.delete()

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="DELETE",
            table_affected="tblPatientDocuments",
            record_ref=f"Doc#{doc_id}",
            notes=f"Deleted document {title}"
        )

        messages.info(request, f"Document '{title}' has been deleted.")

    return redirect('document_list', mr_no=mr_no)
