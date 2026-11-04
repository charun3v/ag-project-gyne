from django.db import models
from django.utils import timezone
from datetime import date
from core.models import State, District, Consultant

class Patient(models.Model):
    """Corresponds to tblPtDetails - Central patient entity."""
    mr_no = models.CharField(
        max_length=64,
        primary_key=True,
        db_column='MR_No',
        verbose_name="MR No.",
        help_text="Unique Medical Record Identifier"
    )
    pt_name = models.CharField(max_length=200, db_column='Pt_name', verbose_name="Patient Name")
    sex = models.CharField(max_length=20, default='Female', db_column='Sex')
    date_of_birth = models.DateField(null=True, blank=True, db_column='Date_Of_birth', verbose_name="Date of Birth")
    dob_is_estimated = models.BooleanField(default=False, db_column='DOB_Is_Estimated', verbose_name="DOB Estimated?")
    date_of_registration = models.DateField(default=date.today, db_column='Date_of_registration', verbose_name="Registration Date")
    
    phone = models.CharField(max_length=30, db_column='Phone', verbose_name="Primary Phone")
    phone_alternate = models.CharField(max_length=30, blank=True, null=True, db_column='Phone_Alternate', verbose_name="Alternate Phone")
    
    address = models.TextField(blank=True, null=True, db_column='Address')
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True, db_column='StateID')
    district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True, blank=True, db_column='DistrictID')
    pincode = models.CharField(max_length=20, blank=True, null=True, db_column='Pincode')
    digipin = models.CharField(max_length=50, blank=True, null=True, db_column='Digipin')
    country = models.CharField(max_length=100, default='India', db_column='Country')
    
    primary_consultant = models.ForeignKey(
        Consultant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='Primary_ConsultantID',
        verbose_name="Primary Consultant"
    )
    notes = models.TextField(blank=True, null=True, db_column='Notes')

    # Audit & soft-delete fields
    entered_by = models.CharField(max_length=100, blank=True, null=True, db_column='EnteredBy')
    entered_on = models.DateTimeField(default=timezone.now, db_column='EnteredOn')
    last_modified_by = models.CharField(max_length=100, blank=True, null=True, db_column='LastModifiedBy')
    last_modified_on = models.DateTimeField(auto_now=True, db_column='LastModifiedOn')
    soft_deleted = models.BooleanField(default=False, db_column='Soft_Deleted')

    class Meta:
        db_table = 'tblPtDetails'
        ordering = ['-date_of_registration', 'pt_name']

    def __str__(self):
        return f"{self.pt_name} [{self.mr_no}]"

    @property
    def age(self):
        """Calculates current age or age at death."""
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    @property
    def diagnosis_display(self):
        """Returns concise primary diagnosis and stage for treatment form headers and displays."""
        diag = self.diagnoses.filter(is_current=True, soft_deleted=False).first() or self.diagnoses.filter(soft_deleted=False).first()
        if diag:
            if diag.diagnosis_description:
                base = diag.diagnosis_description
                if diag.stage_text and f"stage" not in base.lower():
                    base = f"{base} (Stage {diag.stage_text})"
            else:
                parts = []
                if diag.primary_site:
                    parts.append(str(diag.primary_site))
                if diag.histology:
                    parts.append(str(diag.histology))
                elif diag.histology_other:
                    parts.append(str(diag.histology_other))
                if diag.stage_text:
                    parts.append(f"Stage {diag.stage_text}")
                base = " - ".join(parts) if parts else "Diagnosed"

            other_count = self.diagnoses.filter(soft_deleted=False).exclude(pk=diag.pk).count()
            if other_count > 0:
                return f"{base} (+{other_count} additional)"
            return base
        return "Not Staged / Unspecified"

    @property
    def display_label(self):
        age_str = f", {self.age}y" if self.age is not None else ""
        return f"{self.pt_name} [{self.mr_no}]{age_str}"
