import os
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from patients.models import Patient

def patient_document_upload_path(instance, filename):
    """Stores files organized securely by patient MR_No and category."""
    # Sanitize MR number for folder naming
    safe_mr = "".join([c if c.isalnum() or c in ('-', '_') else '_' for c in instance.patient.mr_no])
    safe_cat = instance.category.lower().replace(' ', '_')
    return os.path.join('private', safe_mr, safe_cat, filename)

class PatientDocument(models.Model):
    """
    Private patient records storage for clinical photos, radiology imaging,
    pathology slide scans, operative videos, and PDF reports.
    """
    CATEGORY_CHOICES = [
        ('clinical_photo', 'Clinical Examination Photo'),
        ('radiology_scan', 'Radiology / MRI / CT Scan'),
        ('pathology_report', 'Pathology / Cytology PDF / Scan'),
        ('operative_video', 'Surgical / Brachy Procedure Video'),
        ('consent_form', 'Informed Consent Form'),
        ('mdt_summary', 'MDT Tumour Board Summary'),
        ('other', 'Other Document'),
    ]

    document_id = models.BigAutoField(primary_key=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='documents', db_column='MR_No')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='clinical_photo')
    title = models.CharField(max_length=200, help_text="Brief descriptive title")
    
    file = models.FileField(upload_to=patient_document_upload_path)
    file_type = models.CharField(max_length=50, blank=True, null=True, help_text="MIME type e.g. image/jpeg, application/pdf, video/mp4")
    file_size_bytes = models.BigIntegerField(default=0)
    
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_on = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, null=True)
    is_confidential = models.BooleanField(default=True)

    class Meta:
        db_table = 'tblPatientDocuments'
        ordering = ['-uploaded_on']

    def __str__(self):
        return f"{self.get_category_display()} - {self.title} ({self.patient.mr_no})"

    @property
    def filename(self):
        return os.path.basename(self.file.name) if self.file else ""

    @property
    def file_extension(self):
        ext = os.path.splitext(self.filename)[1].lower()
        return ext[1:] if ext.startswith('.') else ext

    @property
    def is_image(self):
        return self.file_extension in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']

    @property
    def is_pdf(self):
        return self.file_extension == 'pdf'

    @property
    def is_video(self):
        return self.file_extension in ['mp4', 'webm', 'mov', 'mkv', 'avi']

    @property
    def file_size_formatted(self):
        bytes_val = self.file_size_bytes or 0
        if bytes_val < 1024:
            return f"{bytes_val} B"
        elif bytes_val < 1024 * 1024:
            return f"{bytes_val / 1024:.1f} KB"
        else:
            return f"{bytes_val / (1024 * 1024):.1f} MB"
