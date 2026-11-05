from django.db import models
from django.utils import timezone
from datetime import date
from patients.models import Patient

# --- Lookup / Reference Tables for Clinical Domain ---

class PrimarySite(models.Model):
    """sbtblPrimarysite"""
    site_id = models.IntegerField(primary_key=True, db_column='PrimarySiteID')
    site = models.CharField(max_length=100)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblPrimarysite'
        ordering = ['display_order', 'site']

    def __str__(self):
        return self.site


class Histology(models.Model):
    """sbtblHistology"""
    histology_id = models.IntegerField(primary_key=True, db_column='HistologyID')
    histology_name = models.CharField(max_length=150)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblHistology'
        ordering = ['display_order', 'histology_name']

    def __str__(self):
        return self.histology_name


class Grade(models.Model):
    """sbtblGrade"""
    grade_id = models.IntegerField(primary_key=True, db_column='GradeID')
    grade_name = models.CharField(max_length=100)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblGrade'
        ordering = ['display_order']

    def __str__(self):
        return self.grade_name


class StagingSystem(models.Model):
    """sbtblStagingSystem"""
    staging_system_id = models.IntegerField(primary_key=True, db_column='StagingSystemID')
    system_name = models.CharField(max_length=100)
    system_version = models.CharField(max_length=50, blank=True, null=True)
    applies_to_disease = models.CharField(max_length=100, blank=True, null=True)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblStagingSystem'
        ordering = ['display_order', 'system_name']

    def __str__(self):
        return f"{self.system_name} {self.system_version or ''}".strip()


class BasisOfDiagnosis(models.Model):
    """sbtblBasisOfDiagnosis"""
    basis_id = models.IntegerField(primary_key=True, db_column='BasisID')
    basis_name = models.CharField(max_length=100)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblBasisOfDiagnosis'
        ordering = ['display_order']

    def __str__(self):
        return self.basis_name


class ECOGScore(models.Model):
    """sbtblECOG"""
    ecog_id = models.IntegerField(primary_key=True, db_column='ECOGID')
    score = models.IntegerField()
    description = models.CharField(max_length=255)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblECOG'
        ordering = ['score']

    def __str__(self):
        return f"ECOG {self.score}: {self.description}"


class EncounterType(models.Model):
    """sbtblEncounterType"""
    encounter_type_id = models.IntegerField(primary_key=True, db_column='EncounterTypeID')
    encounter_type_name = models.CharField(max_length=100)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblEncounterType'
        ordering = ['display_order']

    def __str__(self):
        return self.encounter_type_name


class SVGRegion(models.Model):
    """sbtblSVGRegions - 65 interactive anatomical pelvic diagram regions"""
    svg_region_id = models.IntegerField(primary_key=True, db_column='SVGRegionID')
    region_code = models.CharField(max_length=100, unique=True, db_column='Region_Code')
    display_label = models.CharField(max_length=150, db_column='Display_Label')
    view_name = models.CharField(max_length=50, blank=True, null=True, db_column='View_Name')
    organ = models.CharField(max_length=100, blank=True, null=True, db_column='Organ')
    position = models.CharField(max_length=100, blank=True, null=True, db_column='Position')
    anatomical_group = models.CharField(max_length=100, blank=True, null=True, db_column='Anatomical_Group')
    default_color = models.CharField(max_length=50, blank=True, null=True, db_column='Default_Color')
    display_order = models.IntegerField(default=1, db_column='Display_Order')
    is_active = models.BooleanField(default=True, db_column='IsActive')

    class Meta:
        db_table = 'sbtblSVGRegions'
        ordering = ['display_order', 'display_label']

    def __str__(self):
        return f"{self.display_label} ({self.region_code})"


# --- Core Clinical Entities ---

class Encounter(models.Model):
    """Corresponds to tblEncounter - Clinical encounters, examinations, and diagram findings."""
    clinical_id = models.BigAutoField(primary_key=True, db_column='ClinicalID')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='encounters', db_column='MR_No')
    encounter_type = models.ForeignKey(EncounterType, on_delete=models.SET_NULL, null=True, blank=True, db_column='EncounterTypeID')
    encounter_date = models.DateField(default=date.today, db_column='Encounter_Date')
    
    height = models.FloatField(null=True, blank=True, db_column='Height', help_text="Height in cm")
    weight = models.FloatField(null=True, blank=True, db_column='Weight', help_text="Weight in kg")
    ecog = models.ForeignKey(ECOGScore, on_delete=models.SET_NULL, null=True, blank=True, db_column='ECOG')
    
    presenting_complaints = models.TextField(blank=True, null=True, db_column='Presenting_Complaints')
    examination_findings = models.TextField(blank=True, null=True, db_column='Examination_Findings')
    prev_tx_history = models.CharField(max_length=255, blank=True, null=True, db_column='Prev_Tx_History')
    
    # Clinical Pelvic Examination Findings
    parametrial_invasion = models.BooleanField(default=False, db_column='Parametrial_Invasion')
    para_left = models.BooleanField(default=False, db_column='Para_Left')
    para_right = models.BooleanField(default=False, db_column='Para_Right')
    para_extent_left_cm = models.FloatField(null=True, blank=True, db_column='Para_Extent_Left_cm')
    para_extent_right_cm = models.FloatField(null=True, blank=True, db_column='Para_Extent_Right_cm')
    
    rectal_invasion = models.BooleanField(default=False, db_column='Rectal_Invasion')
    bladder_invasion = models.BooleanField(default=False, db_column='Bladder_Invasion')
    
    tumour_size_cm = models.FloatField(null=True, blank=True, db_column='Tumour_Size_cm')
    tumour_size_2_cm = models.FloatField(null=True, blank=True, db_column='Tumour_Size_2_cm')
    tumour_size_3_cm = models.FloatField(null=True, blank=True, db_column='Tumour_Size_3_cm', verbose_name="Tumour Thickness (cm)")
    
    ebrt_given = models.BooleanField(default=False, db_column='EBRT_Given')
    linked_ebrt_course_id = models.IntegerField(null=True, blank=True, db_column='Linked_EBRTCourseID')
    tandem_sounded = models.BooleanField(default=False, db_column='Tandem_Sounded')
    tandem_length_cm = models.FloatField(null=True, blank=True, db_column='Tandem_Length_cm')
    autopopulated_from_clinical_id = models.IntegerField(null=True, blank=True, db_column='AutoPopulated_From_ClinicalID')

    # Approval and locking
    findings_approved_by = models.CharField(max_length=100, blank=True, null=True, db_column='Findings_Approved_By')
    findings_approved_on = models.DateTimeField(null=True, blank=True, db_column='Findings_Approved_On')
    findings_locked = models.BooleanField(default=False, db_column='Findings_Locked')
    
    svg_approved_by = models.CharField(max_length=100, blank=True, null=True, db_column='SVG_Approved_By')
    svg_approved_on = models.DateTimeField(null=True, blank=True, db_column='SVG_Approved_On')
    svg_locked = models.BooleanField(default=False, db_column='SVG_Locked')

    # Audit fields
    entered_by = models.CharField(max_length=100, blank=True, null=True, db_column='EnteredBy')
    entered_on = models.DateTimeField(default=timezone.now, db_column='EnteredOn')
    last_modified_by = models.CharField(max_length=100, blank=True, null=True, db_column='LastModifiedBy')
    last_modified_on = models.DateTimeField(auto_now=True, db_column='LastModifiedOn')
    soft_deleted = models.BooleanField(default=False, db_column='Soft_Deleted')

    class Meta:
        db_table = 'tblEncounter'
        ordering = ['-encounter_date', '-clinical_id']

    def __str__(self):
        enc_type = self.encounter_type.encounter_type_name if self.encounter_type else "Encounter"
        return f"{self.patient.pt_name} - {enc_type} ({self.encounter_date})"


class ClinicalSVGFinding(models.Model):
    """Corresponds to tblClinicalSVGFindings - Marked regions from the IBS Clinical Diagram."""
    svg_finding_id = models.BigAutoField(primary_key=True, db_column='SVGFindingID')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='svg_findings', db_column='EncounterID')
    region = models.ForeignKey(SVGRegion, on_delete=models.CASCADE, related_name='findings', db_column='SVGRegionID')
    
    involvement_type = models.CharField(max_length=100, blank=True, null=True, db_column='Involvement_Type')
    lesion_type = models.CharField(max_length=100, blank=True, null=True, db_column='Lesion_Type')
    depth_of_invasion = models.CharField(max_length=100, blank=True, null=True, db_column='Depth_Of_Invasion')
    bleeds_on_touch = models.BooleanField(default=False, db_column='Bleeds_On_Touch')
    necrotic = models.BooleanField(default=False, db_column='Necrotic')
    region_notes = models.TextField(blank=True, null=True, db_column='Region_Notes')
    
    entered_by = models.CharField(max_length=100, blank=True, null=True, db_column='EnteredBy')
    entered_on = models.DateTimeField(default=timezone.now, db_column='EnteredOn')
    last_modified_by = models.CharField(max_length=100, blank=True, null=True, db_column='LastModifiedBy')
    last_modified_on = models.DateTimeField(auto_now=True, db_column='LastModifiedOn')
    soft_deleted = models.BooleanField(default=False, db_column='Soft_Deleted')
    approved_by = models.CharField(max_length=100, blank=True, null=True, db_column='Approved_By')
    approved_on = models.DateTimeField(null=True, blank=True, db_column='Approved_On')
    approval_locked = models.BooleanField(default=False, db_column='Approval_Locked')

    class Meta:
        db_table = 'tblClinicalSVGFindings'
        unique_together = ('encounter', 'region')

    def __str__(self):
        return f"Encounter #{self.encounter_id} - {self.region.display_label}"


class ClinicalHistory(models.Model):
    """Corresponds to tblHistory - Longitudinal clinical history and comorbidities."""
    history_id = models.BigAutoField(primary_key=True, db_column='HistoryID')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='histories', db_column='MR_No')
    encounter = models.ForeignKey(Encounter, on_delete=models.SET_NULL, null=True, blank=True, db_column='EncounterID')
    snapshot_date = models.DateField(default=date.today, db_column='Snapshot_Date')
    
    hpi = models.TextField(blank=True, null=True, db_column='HPI', verbose_name="History of Present Illness")
    past_med_surg = models.TextField(blank=True, null=True, db_column='Past_Med_Surg', verbose_name="Past Medical / Surgical History")
    
    # Comorbidities
    hypertension = models.BooleanField(default=False, db_column='Hypertension')
    hypothyroidism = models.BooleanField(default=False, db_column='Hypothyroidism')
    seizures = models.BooleanField(default=False, db_column='Seizures')
    diabetic = models.BooleanField(default=False, db_column='Diabetic')
    comorbidity_others = models.BooleanField(default=False, db_column='Comorbidity_Others')
    comorbidity_notes = models.TextField(blank=True, null=True, db_column='Comorbidity_Notes')
    
    # Habits
    smoking = models.BooleanField(default=False, db_column='Smoking')
    alcohol = models.BooleanField(default=False, db_column='Alcohol')
    tobacco_chewing = models.BooleanField(default=False, db_column='Tobacco_Chewing')
    habits_others = models.BooleanField(default=False, db_column='Habits_Others')
    habits_notes = models.TextField(blank=True, null=True, db_column='Habits_Notes')
    
    # Presenting Symptoms
    bleeding_pv = models.BooleanField(default=False, db_column='Bleeding_PV', verbose_name="Bleeding P/V")
    water_discharge_pv = models.BooleanField(default=False, db_column='Water_Discharge_PV', verbose_name="Watery Discharge P/V")
    dyspareunia = models.BooleanField(default=False, db_column='Dyspareunia')
    loin_pain = models.BooleanField(default=False, db_column='Loin_Pain')
    
    # Prior Treatments
    prior_radiation = models.BooleanField(default=False, db_column='Prior_Radiation')
    prior_radiation_details = models.TextField(blank=True, null=True, db_column='Prior_Radiation_Details')
    previous_surgery = models.BooleanField(default=False, db_column='Previous_Surgery')
    previous_surgery_details = models.TextField(blank=True, null=True, db_column='Previous_Surgery_Details')

    # Audit & approval
    entered_by = models.CharField(max_length=100, blank=True, null=True, db_column='EnteredBy')
    entered_on = models.DateTimeField(default=timezone.now, db_column='EnteredOn')
    last_modified_by = models.CharField(max_length=100, blank=True, null=True, db_column='LastModifiedBy')
    last_modified_on = models.DateTimeField(auto_now=True, db_column='LastModifiedOn')
    soft_deleted = models.BooleanField(default=False, db_column='Soft_Deleted')

    class Meta:
        db_table = 'tblHistory'
        ordering = ['-snapshot_date', '-history_id']

    def __str__(self):
        return f"History ({self.snapshot_date}) - {self.patient.pt_name}"


class Diagnosis(models.Model):
    """Corresponds to tblDiagnosis - Oncology diagnosis and staging."""
    diagnosis_id = models.BigAutoField(primary_key=True, db_column='DiagnosisID')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='diagnoses', db_column='MR_No')
    diagnosis_sequence = models.IntegerField(default=1, db_column='Diagnosis_Sequence')
    date_of_diagnosis = models.DateField(default=date.today, db_column='Date_Of_Diagnosis')
    
    primary_site = models.ForeignKey(PrimarySite, on_delete=models.SET_NULL, null=True, blank=True, db_column='PrimarySiteID')
    diagnosis_description = models.CharField(max_length=255, blank=True, null=True, db_column='Diagnosis_Description')
    
    histology = models.ForeignKey(Histology, on_delete=models.SET_NULL, null=True, blank=True, db_column='HistologyID')
    histology_other = models.CharField(max_length=200, blank=True, null=True, db_column='Histology_Other')
    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True, blank=True, db_column='GradeID')
    basis = models.ForeignKey(BasisOfDiagnosis, on_delete=models.SET_NULL, null=True, blank=True, db_column='BasisID')
    
    staging_system = models.ForeignKey(StagingSystem, on_delete=models.SET_NULL, null=True, blank=True, db_column='StagingSystemID')
    stage_text = models.CharField(max_length=50, blank=True, null=True, db_column='Stage_Text', help_text="e.g. IIB, IIIC1")
    t_status = models.CharField(max_length=50, blank=True, null=True, db_column='T_Status')
    n_status = models.CharField(max_length=50, blank=True, null=True, db_column='N_Status')
    m_status = models.CharField(max_length=50, blank=True, null=True, db_column='M_Status')
    laterality = models.CharField(max_length=50, blank=True, null=True, db_column='Laterality')
    
    pathology_text = models.TextField(blank=True, null=True, db_column='Pathology_Text')
    comments = models.TextField(blank=True, null=True, db_column='Comments')
    is_current = models.BooleanField(default=True, db_column='Is_Current')

    # Audit fields
    entered_by = models.CharField(max_length=100, blank=True, null=True, db_column='EnteredBy')
    entered_on = models.DateTimeField(default=timezone.now, db_column='EnteredOn')
    last_modified_by = models.CharField(max_length=100, blank=True, null=True, db_column='LastModifiedBy')
    last_modified_on = models.DateTimeField(auto_now=True, db_column='LastModifiedOn')
    soft_deleted = models.BooleanField(default=False, db_column='Soft_Deleted')

    class Meta:
        db_table = 'tblDiagnosis'
        ordering = ['-date_of_diagnosis', 'diagnosis_sequence']

    def __str__(self):
        site_str = self.primary_site.site if self.primary_site else "Unknown Site"
        stage_str = f" Stage {self.stage_text}" if self.stage_text else ""
        return f"{self.patient.pt_name} - {site_str}{stage_str}"
