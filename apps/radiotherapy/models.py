from django.db import models
from django.utils import timezone
from datetime import date
from patients.models import Patient
from core.models import Consultant

# --- Lookup / Reference Tables for Radiotherapy ---

class EBRTIntent(models.Model):
    """sbtblEBRTIntent (Radical, Adjuvant, Palliative, Recurrence)"""
    intent_id = models.IntegerField(primary_key=True, db_column='EBRTIntentID')
    intent_name = models.CharField(max_length=100)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblEBRTIntent'
        ordering = ['display_order']

    def __str__(self):
        return self.intent_name


class EBRTTechnique(models.Model):
    """sbtblEBRTechnique (3DCRT, IMRT, VMAT, Tomotherapy, 2D)"""
    technique_id = models.IntegerField(primary_key=True, db_column='RTTechniqueID')
    technique_name = models.CharField(max_length=100)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblEBRTechnique'
        ordering = ['display_order']

    def __str__(self):
        return self.technique_name


class EBRTSite(models.Model):
    """sbtblEBRTSite (Whole Pelvis, Parametrial Boost, Para-aortic Nodes)"""
    site_id = models.IntegerField(primary_key=True, db_column='EBRTSiteID')
    site_name = models.CharField(max_length=100)
    site_category = models.CharField(max_length=100, blank=True, null=True)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblEBRTSite'
        ordering = ['display_order']

    def __str__(self):
        return self.site_name


class TreatmentCentre(models.Model):
    """sbtblTreatmentCentre"""
    centre_id = models.IntegerField(primary_key=True, db_column='TreatmentCentreID')
    centre_code = models.CharField(max_length=50)
    centre_name = models.CharField(max_length=150)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblTreatmentCentre'
        ordering = ['display_order']

    def __str__(self):
        return self.centre_name


class RTMachine(models.Model):
    """sbtblRTMachine (Linac 1, Linac 2, CyberKnife, etc.)"""
    machine_id = models.IntegerField(primary_key=True, db_column='RTMachineID')
    machine_name = models.CharField(max_length=100)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblRTMachine'
        ordering = ['display_order']

    def __str__(self):
        return self.machine_name


class InterruptionReason(models.Model):
    """sbtblInterruptionReason"""
    reason_id = models.IntegerField(primary_key=True, db_column='InterruptionReasonID')
    reason_name = models.CharField(max_length=150)
    allow_custom_text = models.BooleanField(default=False)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblInterruptionReason'
        ordering = ['display_order']

    def __str__(self):
        return self.reason_name


class TreatmentCourseStatus(models.Model):
    """sbtblTreatmentCourseStatus (In Progress, Completed, Discontinued, Planned)"""
    course_status_id = models.IntegerField(primary_key=True, db_column='CourseStatusID')
    status_name = models.CharField(max_length=100)
    is_terminal = models.BooleanField(default=False)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblTreatmentCourseStatus'
        ordering = ['display_order']

    def __str__(self):
        return self.status_name


class BrachySourceType(models.Model):
    """sbtblBrachySourceType (Ir-192 HDR, Co-60 HDR, Cs-137 LDR)"""
    source_id = models.IntegerField(primary_key=True, db_column='BrachySourceID')
    source_name = models.CharField(max_length=100)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblBrachySourceType'
        ordering = ['display_order']

    def __str__(self):
        return self.source_name


class BrachyDosing(models.Model):
    """sbtblBrachyDosing (Manchester Point A, ICRU 38, GEC-ESTRO 3D)"""
    dosing_id = models.IntegerField(primary_key=True, db_column='BrachyDosingID')
    dosing_point = models.CharField(max_length=100)
    dosing_system = models.CharField(max_length=100, blank=True, null=True)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblBrachyDosing'
        ordering = ['display_order']

    def __str__(self):
        return self.dosing_point


class ApplicatorTypeQuerySet(models.QuerySet):
    def filter(self, *args, **kwargs):
        new_kwargs = {}
        for k, v in kwargs.items():
            if k == 'is_active':
                new_kwargs['active'] = v
            elif k.startswith('is_active__'):
                new_kwargs['active__' + k[len('is_active__'):]] = v
            elif k == 'applicator_name':
                new_kwargs['name'] = v
            elif k.startswith('applicator_name__'):
                new_kwargs['name__' + k[len('applicator_name__'):]] = v
            elif k == 'applicator_id':
                new_kwargs['id'] = v
            elif k.startswith('applicator_id__'):
                new_kwargs['id__' + k[len('applicator_id__'):]] = v
            else:
                new_kwargs[k] = v
        return super().filter(*args, **new_kwargs)


class ApplicatorType(models.Model):
    """sbtblBrachyApplicator - Configurable Applicator Types (Tandem, Ovoids, Ring, Needles, etc.)"""
    id = models.AutoField(primary_key=True, db_column='BrachyApplicatorID')
    name = models.CharField(max_length=150)
    active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=1)

    objects = ApplicatorTypeQuerySet.as_manager()

    class Meta:
        db_table = 'sbtblBrachyApplicator'
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name

    # Backwards compatibility properties / aliases
    @property
    def applicator_id(self):
        return self.id

    @applicator_id.setter
    def applicator_id(self, val):
        self.id = val

    @property
    def applicator_name(self):
        return self.name

    @applicator_name.setter
    def applicator_name(self, val):
        self.name = val

    @property
    def is_active(self):
        return self.active

    @is_active.setter
    def is_active(self, val):
        self.active = val


# Compatibility alias for existing codebase
BrachyApplicator = ApplicatorType


class ApplicatorMeasurementDefinition(models.Model):
    """
    Catalog of measurable physical applicator dimensions and needle counts.
    (e.g., tandem length, ovoid diameter, ovoid length, ring diameter, number of needles)
    """
    DATA_TYPE_CHOICES = [
        ('decimal', 'Decimal (Floating Point)'),
        ('integer', 'Whole Integer'),
    ]

    id = models.AutoField(primary_key=True)
    code = models.CharField(max_length=50, unique=True, help_text="e.g. tandem_length_cm, ovoid_diameter_mm")
    label = models.CharField(max_length=100, help_text="Clinical display label")
    data_type = models.CharField(max_length=20, default='decimal', choices=DATA_TYPE_CHOICES)
    unit = models.CharField(max_length=20, blank=True, default='', help_text="Unit string, e.g. cm, mm")
    minimum_value = models.FloatField(null=True, blank=True, help_text="Default clinical minimum value")
    maximum_value = models.FloatField(null=True, blank=True, help_text="Default clinical maximum value")
    active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=1)

    class Meta:
        db_table = 'sbtblApplicatorMeasurementDefinition'
        ordering = ['display_order', 'id']

    def __str__(self):
        unit_str = f" ({self.unit})" if self.unit else ""
        return f"{self.label}{unit_str} [{self.code}]"


class ApplicatorFieldRule(models.Model):
    """
    Administrator-configurable mapping between ApplicatorType and ApplicatorMeasurementDefinition.
    Specifies whether a measurement is enabled, mandatory (required), display order, and optional range overrides.
    """
    id = models.AutoField(primary_key=True)
    applicator_type = models.ForeignKey(
        ApplicatorType,
        on_delete=models.CASCADE,
        related_name='field_rules',
        db_column='ApplicatorTypeID'
    )
    measurement_definition = models.ForeignKey(
        ApplicatorMeasurementDefinition,
        on_delete=models.CASCADE,
        related_name='applicator_rules',
        db_column='MeasurementDefID'
    )
    enabled = models.BooleanField(default=True)
    required = models.BooleanField(default=True)
    display_order = models.IntegerField(default=1)
    min_value_override = models.FloatField(null=True, blank=True, help_text="Optional override for minimum value")
    max_value_override = models.FloatField(null=True, blank=True, help_text="Optional override for maximum value")

    class Meta:
        db_table = 'sbtblApplicatorFieldRule'
        unique_together = ('applicator_type', 'measurement_definition')
        ordering = ['display_order', 'id']

    def __str__(self):
        status = "Required" if self.required else ("Enabled" if self.enabled else "Disabled")
        return f"{self.applicator_type.name} -> {self.measurement_definition.label} ({status})"

    def get_minimum_value(self):
        if self.min_value_override is not None:
            return self.min_value_override
        return self.measurement_definition.minimum_value

    def get_maximum_value(self):
        if self.max_value_override is not None:
            return self.max_value_override
        return self.measurement_definition.maximum_value


class BrachyImageGuidance(models.Model):
    """sbtblBrachyImageGuidance (CT, MRI, Ultrasound, Orthogonal X-ray)"""
    guidance_id = models.IntegerField(primary_key=True, db_column='BrachyImageGuidanceID')
    guidance_name = models.CharField(max_length=100)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblBrachyImageGuidance'
        ordering = ['display_order']

    def __str__(self):
        return self.guidance_name


class AnaesthesiaType(models.Model):
    """sbtblAnaesthesiaType (Spinal, General, Sedation, Local)"""
    anaesthesia_id = models.IntegerField(primary_key=True, db_column='AnaesthesiaTypeID')
    anaesthesia_name = models.CharField(max_length=100)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblAnaesthesiaType'
        ordering = ['display_order']

    def __str__(self):
        return self.anaesthesia_name


class BrachySessionStatus(models.Model):
    """sbtblBrachySessionStatus"""
    status_id = models.IntegerField(primary_key=True, db_column='BrachySessionStatusID')
    status_name = models.CharField(max_length=100)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblBrachySessionStatus'
        ordering = ['display_order']

    def __str__(self):
        return self.status_name


class BrachyFractionStatus(models.Model):
    """sbtblBrachyFractionStatus"""
    status_id = models.IntegerField(primary_key=True, db_column='BrachyFractionStatusID')
    status_name = models.CharField(max_length=100)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblBrachyFractionStatus'
        ordering = ['display_order']

    def __str__(self):
        return self.status_name


class BrachyISTemplate(models.Model):
    """sbtblBrachyISTemplate (Interstitial Template)"""
    template_id = models.IntegerField(primary_key=True, db_column='ID')
    template_name = models.CharField(max_length=100, db_column='IS_Template_name')
    display_order = models.IntegerField(default=1, db_column='DislayOrder')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblBrachyISTemplate'
        ordering = ['display_order']

    def __str__(self):
        return self.template_name


# --- Core Radiotherapy Entities ---

class EBRTCourse(models.Model):
    """Corresponds to tblEBRTCourse - External Beam Radiation Therapy Course."""
    ebrt_course_id = models.BigAutoField(primary_key=True, db_column='EBRTCourseID')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='ebrt_courses', db_column='MR_No')
    course_sequence = models.IntegerField(default=1, db_column='Course_Sequence')
    
    ebrt_intent = models.ForeignKey(EBRTIntent, on_delete=models.SET_NULL, null=True, blank=True, db_column='EBRTIntentID')
    ebrt_technique = models.ForeignKey(EBRTTechnique, on_delete=models.SET_NULL, null=True, blank=True, db_column='EBRTTechniqueID')
    treatment_centre = models.ForeignKey(TreatmentCentre, on_delete=models.SET_NULL, null=True, blank=True, db_column='TreatmentCentreID')
    initial_rt_machine = models.ForeignKey(RTMachine, on_delete=models.SET_NULL, null=True, blank=True, db_column='InitialRTMachineID')
    course_status = models.ForeignKey(TreatmentCourseStatus, on_delete=models.SET_NULL, null=True, blank=True, db_column='CourseStatusID')
    
    total_dose_gy = models.FloatField(null=True, blank=True, db_column='Total_Dose_Gy')
    total_fractions = models.IntegerField(null=True, blank=True, db_column='Total_Fractions')
    dose_per_fraction_gy = models.FloatField(null=True, blank=True, db_column='Dose_Per_Fraction_Gy')
    
    ebrt_start_date = models.DateField(null=True, blank=True, db_column='EBRT_Start_Date')
    ebrt_end_date = models.DateField(null=True, blank=True, db_column='EBRT_End_Date')
    
    simulation_date = models.DateField(null=True, blank=True, db_column='Simulation_Date')
    contouring_date = models.DateField(null=True, blank=True, db_column='Contouring_Date')
    plan_approval_date = models.DateField(null=True, blank=True, db_column='Plan_Approval_Date')
    
    treatment_interrupted = models.BooleanField(default=False, db_column='Treatment_Interrupted')
    interruption_days = models.IntegerField(default=0, db_column='Interruption_Days')
    long_gap_notes = models.TextField(blank=True, null=True, db_column='Long_Gap_Notes')
    
    treatment_completed = models.BooleanField(default=False, db_column='Treatment_Completed')
    completion_notes = models.TextField(blank=True, null=True, db_column='Completion_Notes')

    # Approval and locking
    is_approved = models.BooleanField(default=False, db_column='Is_Approved')
    approved_by = models.CharField(max_length=100, blank=True, null=True, db_column='Approved_By')
    approved_on = models.DateTimeField(null=True, blank=True, db_column='Approved_On')
    approval_locked = models.BooleanField(default=False, db_column='Approval_Locked')

    entered_by = models.CharField(max_length=100, blank=True, null=True, db_column='EnteredBy')
    entered_on = models.DateTimeField(default=timezone.now, db_column='EnteredOn')
    last_modified_by = models.CharField(max_length=100, blank=True, null=True, db_column='LastModifiedBy')
    last_modified_on = models.DateTimeField(auto_now=True, db_column='LastModifiedOn')
    soft_deleted = models.BooleanField(default=False, db_column='Soft_Deleted')

    class Meta:
        db_table = 'tblEBRTCourse'
        ordering = ['course_sequence']

    def __str__(self):
        dose_str = f" ({self.total_dose_gy} Gy / {self.total_fractions}#)" if self.total_dose_gy else ""
        return f"EBRT Course {self.course_sequence}{dose_str} - {self.patient.pt_name}"


class EBRTCourseSite(models.Model):
    """Corresponds to tblEBRTCourseSite"""
    ebrt_course_site_id = models.BigAutoField(primary_key=True, db_column='EBRTCourseSiteID')
    ebrt_course = models.ForeignKey(EBRTCourse, on_delete=models.CASCADE, related_name='sites', db_column='EBRTCourseID')
    ebrt_site = models.ForeignKey(EBRTSite, on_delete=models.CASCADE, db_column='EBRTSiteID')

    class Meta:
        db_table = 'tblEBRTCourseSite'
        unique_together = ('ebrt_course', 'ebrt_site')

    def __str__(self):
        return f"{self.ebrt_site.site_name} in Course #{self.ebrt_course_id}"


class EBRTInterruption(models.Model):
    """Corresponds to tblEBRTInterruptionReasons"""
    ebrt_interruption_id = models.BigAutoField(primary_key=True, db_column='EBRTInterruptionID')
    ebrt_course = models.ForeignKey(EBRTCourse, on_delete=models.CASCADE, related_name='interruptions', db_column='EBRTCourseID')
    interruption_reason = models.ForeignKey(InterruptionReason, on_delete=models.SET_NULL, null=True, blank=True, db_column='InterruptionReasonID')
    custom_text = models.CharField(max_length=150, blank=True, null=True, db_column='Custom_Text')
    days_lost = models.IntegerField(default=1, db_column='Days_Lost')
    interruption_start_date = models.DateField(null=True, blank=True, db_column='Interruption_Start_Date')
    interruption_end_date = models.DateField(null=True, blank=True, db_column='Interruption_End_Date')
    notes = models.CharField(max_length=255, blank=True, null=True, db_column='Notes')

    class Meta:
        db_table = 'tblEBRTInterruptionReasons'

    def __str__(self):
        reason = self.interruption_reason.reason_name if self.interruption_reason else (self.custom_text or "Interruption")
        return f"{reason}: {self.days_lost} days lost"


class BrachyCourse(models.Model):
    """Corresponds to tblBrachyCourse - Brachytherapy Course."""
    brachy_course_id = models.BigAutoField(primary_key=True, db_column='BrachyCourseID')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='brachy_courses', db_column='MR_No')
    course_sequence = models.IntegerField(default=1, db_column='Course_Sequence')
    brachy_received = models.BooleanField(default=True, db_column='Brachy_Received')
    
    brachy_source = models.ForeignKey(BrachySourceType, on_delete=models.SET_NULL, null=True, blank=True, db_column='BrachySourceID')
    brachy_dosing = models.ForeignKey(BrachyDosing, on_delete=models.SET_NULL, null=True, blank=True, db_column='BrachyDosingID')
    treatment_centre = models.ForeignKey(TreatmentCentre, on_delete=models.SET_NULL, null=True, blank=True, db_column='TreatmentCentreID')
    course_status = models.ForeignKey(TreatmentCourseStatus, on_delete=models.SET_NULL, null=True, blank=True, db_column='CourseStatusID')
    linked_ebrt_course = models.ForeignKey(EBRTCourse, on_delete=models.SET_NULL, null=True, blank=True, db_column='Linked_EBRTCourseID')
    
    prescription_dose_gy = models.FloatField(null=True, blank=True, db_column='Prescription_Dose_Gy')
    total_fractions_planned = models.IntegerField(default=3, db_column='Total_Fractions_Planned')
    total_fractions_delivered = models.IntegerField(default=0, db_column='Total_Fractions_Delivered')
    
    brachy_start_date = models.DateField(null=True, blank=True, db_column='Brachy_Start_Date')
    brachy_end_date = models.DateField(null=True, blank=True, db_column='Brachy_End_Date')
    
    # Radiobiological Tissue Parameters (Linear-Quadratic Model)
    alpha_beta_tumor = models.FloatField(default=10.0, db_column='AlphaBeta_Tumor', help_text="Tumor acute response (Gy)")
    alpha_beta_bladder = models.FloatField(default=3.0, db_column='AlphaBeta_Bladder', help_text="Bladder late response (Gy)")
    alpha_beta_rectum = models.FloatField(default=3.0, db_column='AlphaBeta_Rectum', help_text="Rectum late response (Gy)")
    alpha_beta_sigmoid = models.FloatField(default=3.0, db_column='AlphaBeta_Sigmoid', help_text="Sigmoid late response (Gy)")
    
    completion_status = models.CharField(max_length=50, blank=True, null=True, db_column='Completion_Status')
    completion_notes = models.TextField(blank=True, null=True, db_column='Completion_Notes')

    # Approval and locking
    is_approved = models.BooleanField(default=False, db_column='Is_Approved')
    approved_by = models.CharField(max_length=100, blank=True, null=True, db_column='Approved_By')
    approved_on = models.DateTimeField(null=True, blank=True, db_column='Approved_On')
    approval_locked = models.BooleanField(default=False, db_column='Approval_Locked')

    entered_by = models.CharField(max_length=100, blank=True, null=True, db_column='EnteredBy')
    entered_on = models.DateTimeField(default=timezone.now, db_column='EnteredOn')
    soft_deleted = models.BooleanField(default=False, db_column='Soft_Deleted')

    class Meta:
        db_table = 'tblBrachyCourse'
        ordering = ['course_sequence']

    def __str__(self):
        return f"Brachy Course {self.course_sequence} - {self.patient.pt_name}"


class BrachySession(models.Model):
    """Corresponds to tblBrachySessions - Applicator insertion sessions."""
    brachy_session_id = models.BigAutoField(primary_key=True, db_column='BrachySessionID')
    brachy_course = models.ForeignKey(BrachyCourse, on_delete=models.CASCADE, related_name='sessions', db_column='BrachyCourseID')
    session_number = models.IntegerField(default=1, db_column='Session_Number')
    session_date = models.DateField(default=date.today, db_column='Session_Date')
    
    applicator = models.ForeignKey(ApplicatorType, on_delete=models.CASCADE, db_column='BrachyApplicatorID', related_name='sessions')
    image_guidance = models.ForeignKey(BrachyImageGuidance, on_delete=models.CASCADE, db_column='BrachyImageGuidanceID')
    anaesthesia_type = models.ForeignKey(AnaesthesiaType, on_delete=models.SET_NULL, null=True, blank=True, db_column='AnaesthesiaTypeID')
    is_template = models.ForeignKey(BrachyISTemplate, on_delete=models.SET_NULL, null=True, blank=True, db_column='ISTemplateID')
    session_status = models.ForeignKey(BrachySessionStatus, on_delete=models.SET_NULL, null=True, blank=True, db_column='BrachySessionStatusID')
    
    procedure_performed_by = models.CharField(max_length=150, blank=True, default='', db_column='Procedure_Performed_By')
    procedure_notes = models.TextField(blank=True, default='', db_column='Procedure_Notes')
    insertion_complications = models.TextField(blank=True, default='None', db_column='Insertion_Complications')
    
    # Applicator physical measurements (configured per ApplicatorType)
    tandem_length_cm = models.FloatField(null=True, blank=True, db_column='Tandem_Length_cm')
    ovoid_diameter_mm = models.FloatField(null=True, blank=True, db_column='Ovoid_Diameter_mm')
    ovoid_length_mm = models.FloatField(null=True, blank=True, db_column='Ovoid_Length_mm')
    legacy_ovoid_size_mm = models.FloatField(null=True, blank=True, db_column='Legacy_Ovoid_Size_mm', help_text="Preserved legacy ovoid size before separation")
    ring_diameter_mm = models.FloatField(null=True, blank=True, db_column='Ring_Diameter_mm')
    needle_count = models.IntegerField(default=0, null=True, blank=True, db_column='Number_Of_Needles')
    
    packing_adequate = models.BooleanField(default=True, db_column='Packing_Adequate')
    imaging_done = models.BooleanField(default=True, db_column='Imaging_Done')
    fractions_planned = models.IntegerField(default=1, db_column='Fractions_Planned')

    # Approval and Historical Record Locking
    is_approved = models.BooleanField(default=False, db_column='Is_Approved')
    approved_by = models.CharField(max_length=100, blank=True, null=True, db_column='Approved_By')
    approved_on = models.DateTimeField(null=True, blank=True, db_column='Approved_On')
    approval_locked = models.BooleanField(default=False, db_column='Approval_Locked')
    approved_rules_snapshot = models.TextField(blank=True, null=True, db_column='Approved_Rules_Snapshot')

    class Meta:
        db_table = 'tblBrachySessions'
        ordering = ['session_number']

    def __str__(self):
        return f"Session #{self.session_number} ({self.session_date}) - {self.applicator.name}"

    @property
    def approved_rules(self):
        import json
        if self.approved_rules_snapshot:
            try:
                return json.loads(self.approved_rules_snapshot)
            except Exception:
                return []
        return []

    @approved_rules.setter
    def approved_rules(self, val):
        import json
        self.approved_rules_snapshot = json.dumps(val) if val else None

    @property
    def number_of_needles(self):
        return self.needle_count if self.needle_count is not None else 0

    @number_of_needles.setter
    def number_of_needles(self, val):
        self.needle_count = val

    @property
    def ovoid_size_mm(self):
        return self.ovoid_diameter_mm or self.legacy_ovoid_size_mm

    @ovoid_size_mm.setter
    def ovoid_size_mm(self, val):
        self.legacy_ovoid_size_mm = val

    def get_applicable_rules(self):
        """Returns the field rules applicable to this session."""
        if self.approval_locked and self.approved_rules:
            return self.approved_rules
        return ApplicatorFieldRule.objects.filter(
            applicator_type=self.applicator,
            measurement_definition__active=True
        ).select_related('measurement_definition').order_by('display_order', 'id')

    def get_rules_snapshot(self):
        """Creates a JSON-serializable snapshot of active rules upon approval."""
        rules = ApplicatorFieldRule.objects.filter(
            applicator_type=self.applicator,
            measurement_definition__active=True
        ).select_related('measurement_definition').order_by('display_order', 'id')
        snapshot = []
        for r in rules:
            snapshot.append({
                'code': r.measurement_definition.code,
                'label': r.measurement_definition.label,
                'enabled': r.enabled,
                'required': r.required,
                'unit': r.measurement_definition.unit,
                'min_value': r.get_minimum_value(),
                'max_value': r.get_maximum_value(),
                'display_order': r.display_order,
            })
        return snapshot


class BrachyFraction(models.Model):
    """Corresponds to tblBrachyFractions - Fraction dosimetry, dwell time, OAR and target volumes."""
    brachy_fraction_id = models.BigAutoField(primary_key=True, db_column='BrachyFractionID')
    brachy_session = models.ForeignKey(BrachySession, on_delete=models.CASCADE, related_name='fractions', db_column='BrachySessionID')
    fraction_number_in_session = models.IntegerField(default=1, db_column='Fraction_Number_In_Session')
    overall_fraction_number = models.IntegerField(default=1, db_column='Overall_Fraction_Number')
    
    fraction_date = models.DateField(default=date.today, db_column='Fraction_Date')
    delivery_start_time = models.TimeField(null=True, blank=True, db_column='Delivery_Start_Time')
    prescribed_dose_gy = models.FloatField(null=True, blank=True, db_column='Prescribed_Dose_Gy')
    dose_delivered_gy = models.FloatField(null=True, blank=True, db_column='Dose_Delivered_Gy')
    total_dwell_time_seconds = models.FloatField(default=0, db_column='Total_Dwell_Time_seconds')
    
    # Organs at Risk (OAR) Doses (Gy)
    bladder_dose_2cc_gy = models.FloatField(null=True, blank=True, db_column='Bladder_Dose_2cc_Gy')
    rectum_dose_2cc_gy = models.FloatField(null=True, blank=True, db_column='Rectum_Dose_2cc_Gy')
    sigmoid_dose_2cc_gy = models.FloatField(null=True, blank=True, db_column='Sigmoid_Dose_2cc_Gy')
    bowel_dose_2cc_gy = models.FloatField(null=True, blank=True, db_column='Bowel_Dose_2cc_Gy')
    bladder_point_dose_gy = models.FloatField(null=True, blank=True, db_column='Bladder_Point_Dose_Gy')
    rectum_point_dose_gy = models.FloatField(null=True, blank=True, db_column='Rectum_Point_Dose_Gy')
    
    # Target Coverage (Gy)
    hrctv_d90_gy = models.FloatField(null=True, blank=True, db_column='HRCTV_D90_Gy')
    hrctv_d98_gy = models.FloatField(null=True, blank=True, db_column='HRCTV_D98_Gy')
    irctv_d90_gy = models.FloatField(null=True, blank=True, db_column='IRCTV_D90_Gy')
    irctv_d98_gy = models.FloatField(null=True, blank=True, db_column='IRCTV_D98_Gy')
    gtv_d98_gy = models.FloatField(null=True, blank=True, db_column='GTV_D98_Gy')
    
    # Volumes (cc)
    volume_hrctv_cc = models.FloatField(null=True, blank=True, db_column='Volume_HRCTV_cc')
    volume_irctv_cc = models.FloatField(null=True, blank=True, db_column='Volume_IRCTV_cc')
    volume_gtv_cc = models.FloatField(null=True, blank=True, db_column='Volume_GTV_cc')
    
    fraction_status = models.ForeignKey(BrachyFractionStatus, on_delete=models.SET_NULL, null=True, blank=True, db_column='BrachyFractionStatusID')
    fraction_notes = models.TextField(blank=True, default='', db_column='Fraction_Notes')

    class Meta:
        db_table = 'tblBrachyFractions'
        ordering = ['overall_fraction_number']

    def __str__(self):
        return f"Fraction #{self.overall_fraction_number}: {self.dose_delivered_gy} Gy ({self.fraction_date})"

    @staticmethod
    def calculate_eqd2(dose, fractions, alpha_beta):
        """
        Calculates EQD2 using standard linear-quadratic equation:
        EQD2 = Dose * ((Dose/Fractions + alpha_beta) / (2.0 + alpha_beta))
        """
        if not dose or not fractions or fractions <= 0 or not alpha_beta or (2.0 + alpha_beta) == 0:
            return 0.0
        d = float(dose) / float(fractions)
        return float(dose) * ((d + float(alpha_beta)) / (2.0 + float(alpha_beta)))
