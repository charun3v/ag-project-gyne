from django.db import models
from django.utils import timezone
from datetime import date
from patients.models import Patient
from radiotherapy.models import EBRTCourse, BrachyCourse

# --- Lookup / Reference Tables for Systemic Chemotherapy ---

class ChemoAgent(models.Model):
    """sbtblChemoAgent (Cisplatin, Carboplatin, Paclitaxel, Gemcitabine, etc.)"""
    agent_id = models.IntegerField(primary_key=True, db_column='ChemoAgentID')
    agent_name = models.CharField(max_length=150)
    agent_class = models.CharField(max_length=100, blank=True, null=True)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblChemoAgent'
        ordering = ['display_order', 'agent_name']

    def __str__(self):
        return self.agent_name


class ChemoRegimen(models.Model):
    """sbtblChemoRegimen (Weekly Cisplatin, TP, Paclitaxel-Carboplatin)"""
    regimen_id = models.IntegerField(primary_key=True, db_column='ChemoRegimenID')
    regimen_code = models.CharField(max_length=50)
    regimen_description = models.CharField(max_length=255)
    typical_indication = models.CharField(max_length=150, blank=True, null=True)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblChemoRegimen'
        ordering = ['display_order']

    def __str__(self):
        return f"{self.regimen_code} ({self.regimen_description})"


class ChemoRoute(models.Model):
    """sbtblChemoRoute (IV Infusion, IV Bolus, Oral)"""
    route_id = models.IntegerField(primary_key=True, db_column='ChemoRouteID')
    route_name = models.CharField(max_length=100)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblChemoRoute'
        ordering = ['display_order']

    def __str__(self):
        return self.route_name


class DoseUnit(models.Model):
    """sbtblDoseUnit (mg/m2, mg total, AUC 5, AUC 6)"""
    unit_id = models.IntegerField(primary_key=True, db_column='DoseUnitID')
    unit_name = models.CharField(max_length=50)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblDoseUnit'
        ordering = ['display_order']

    def __str__(self):
        return self.unit_name


class NACTStatus(models.Model):
    """sbtblNACTStatus"""
    status_id = models.IntegerField(primary_key=True, db_column='NACTStatusID')
    status_name = models.CharField(max_length=100)
    is_terminal = models.BooleanField(default=False, db_column='IsTerminal')
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblNACTStatus'
        ordering = ['display_order']

    def __str__(self):
        return self.status_name


class ResponseStatus(models.Model):
    """sbtblResponseStatus (Complete Response, Partial Response, Stable Disease, Progression)"""
    response_id = models.IntegerField(primary_key=True, db_column='ResponseID')
    response_code = models.CharField(max_length=50)
    response_description = models.CharField(max_length=150)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblResponseStatus'
        ordering = ['display_order']

    def __str__(self):
        return f"{self.response_code} - {self.response_description}"


# --- Concurrent Chemotherapy (with EBRT) ---

class ConcurrentChemoCourse(models.Model):
    """Corresponds to tblConcurrentChemoCourse"""
    conc_chemo_course_id = models.BigAutoField(primary_key=True, db_column='ConcChemoCourseID')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='concurrent_chemo_courses', db_column='MR_No')
    concurrent_received = models.BooleanField(default=False, db_column='Concurrent_Received')
    chemo_regimen = models.ForeignKey(ChemoRegimen, on_delete=models.SET_NULL, null=True, blank=True, db_column='ChemoRegimenID')
    cycle_frequency_days = models.IntegerField(default=7, db_column='Cycle_Frequency_Days')
    planned_cycles = models.IntegerField(default=5, db_column='Planned_Cycles')
    received_cycles = models.IntegerField(default=0, db_column='Received_Cycles')
    
    conc_chemo_start_date = models.DateField(null=True, blank=True, db_column='ConcChemo_Start_Date')
    conc_chemo_end_date = models.DateField(null=True, blank=True, db_column='ConcChemo_End_Date')
    linked_ebrt_course = models.ForeignKey(EBRTCourse, on_delete=models.SET_NULL, null=True, blank=True, related_name='concurrent_chemo_courses', db_column='Linked_EBRTCourseID')
    
    completion_status = models.CharField(max_length=50, blank=True, null=True, db_column='Completion_Status')
    discontinuation_reason = models.TextField(blank=True, null=True, db_column='Discontinuation_Reason')
    notes = models.TextField(blank=True, null=True, db_column='Notes')

    # Approval and locking
    is_approved = models.BooleanField(default=False, db_column='Is_Approved')
    approved_by = models.CharField(max_length=100, blank=True, null=True, db_column='Approved_By')
    approved_on = models.DateTimeField(null=True, blank=True, db_column='Approved_On')
    approval_locked = models.BooleanField(default=False, db_column='Approval_Locked')

    entered_by = models.CharField(max_length=100, blank=True, null=True, db_column='EnteredBy')
    entered_on = models.DateTimeField(default=timezone.now, db_column='EnteredOn')
    soft_deleted = models.BooleanField(default=False, db_column='Soft_Deleted')

    class Meta:
        db_table = 'tblConcurrentChemoCourse'

    def __str__(self):
        reg = self.chemo_regimen.regimen_code if self.chemo_regimen else "Chemo"
        return f"Concurrent {reg} ({self.received_cycles}/{self.planned_cycles} cycles) - {self.patient.pt_name}"


class ConcurrentChemoCycle(models.Model):
    """Corresponds to tblConcurrentChemoCycles"""
    conc_chemo_cycle_id = models.BigAutoField(primary_key=True, db_column='ConcChemoCycleID')
    course = models.ForeignKey(ConcurrentChemoCourse, on_delete=models.CASCADE, related_name='cycles', db_column='ConcChemoCourseID')
    cycle_number = models.IntegerField(default=1, db_column='Cycle_Number')
    cycle_date = models.DateField(default=date.today, db_column='Cycle_Date')
    cycle_status = models.CharField(max_length=50, blank=True, null=True, default='Administered', db_column='Cycle_Status')
    pre_cycle_notes = models.TextField(blank=True, null=True, db_column='Pre_Cycle_Notes')
    cycle_toxicity = models.TextField(blank=True, null=True, db_column='Cycle_Toxicity')
    post_cycle_notes = models.TextField(blank=True, null=True, db_column='Post_Cycle_Notes')

    class Meta:
        db_table = 'tblConcurrentChemoCycles'
        ordering = ['cycle_number']

    def __str__(self):
        return f"Cycle #{self.cycle_number} ({self.cycle_date})"


class ConcurrentChemoDrug(models.Model):
    """Corresponds to tblConcurrentChemoDrugs"""
    conc_chemo_drug_id = models.BigAutoField(primary_key=True, db_column='ConcChemoDrugID')
    cycle = models.ForeignKey(ConcurrentChemoCycle, on_delete=models.CASCADE, related_name='drugs', db_column='ConcChemoCycleID')
    chemo_agent = models.ForeignKey(ChemoAgent, on_delete=models.CASCADE, db_column='ChemoAgentID')
    dose = models.FloatField(null=True, blank=True, db_column='Dose')
    dose_unit = models.ForeignKey(DoseUnit, on_delete=models.SET_NULL, null=True, blank=True, db_column='DoseUnitID')
    no_of_days = models.IntegerField(default=1, db_column='No_Of_Days')
    day_of_administration = models.IntegerField(default=1, db_column='Day_Of_Administration')
    dose_mg = models.FloatField(null=True, blank=True, db_column='Dose_mg')
    dose_per_m2 = models.FloatField(null=True, blank=True, db_column='Dose_per_m2')
    bsa_m2 = models.FloatField(null=True, blank=True, db_column='BSA_m2')
    chemo_route = models.ForeignKey(ChemoRoute, on_delete=models.SET_NULL, null=True, blank=True, db_column='ChemoRouteID')
    administered = models.BooleanField(default=True, db_column='Administered')
    reason_if_not_administered = models.CharField(max_length=255, blank=True, null=True, db_column='Reason_If_Not_Administered')

    class Meta:
        db_table = 'tblConcurrentChemoDrugs'

    def __str__(self):
        return f"{self.chemo_agent.agent_name}: {self.dose} {self.dose_unit.unit_name if self.dose_unit else ''}"


# --- Neoadjuvant Chemotherapy (NACT) ---

class NACTCourse(models.Model):
    """Corresponds to tblNACTCourse"""
    nact_course_id = models.BigAutoField(primary_key=True, db_column='NACTCourseID')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='nact_courses', db_column='MR_No')
    course_sequence = models.IntegerField(default=1, db_column='Course_Sequence')
    nact_received = models.BooleanField(default=False, db_column='NACT_Received')
    chemo_regimen = models.ForeignKey(ChemoRegimen, on_delete=models.SET_NULL, null=True, blank=True, db_column='ChemoRegimenID')
    cycle_frequency_days = models.IntegerField(default=21, db_column='Cycle_Frequency_Days')
    planned_cycles = models.IntegerField(default=3, db_column='Planned_Cycles')
    received_cycles = models.IntegerField(default=0, db_column='Received_Cycles')
    
    nact_start_date = models.DateField(null=True, blank=True, db_column='NACT_Start_Date')
    nact_end_date = models.DateField(null=True, blank=True, db_column='NACT_End_Date')
    response_to_nact = models.ForeignKey(ResponseStatus, on_delete=models.SET_NULL, null=True, blank=True, db_column='ResponseID')
    nact_status = models.ForeignKey(NACTStatus, on_delete=models.SET_NULL, null=True, blank=True, db_column='NACTStatusID')

    # Forward links to subsequent definitive treatment
    linked_ebrt_course = models.ForeignKey(EBRTCourse, on_delete=models.SET_NULL, null=True, blank=True, related_name='nact_courses', db_column='Linked_EBRTCourseID')
    linked_brachy_course = models.ForeignKey(BrachyCourse, on_delete=models.SET_NULL, null=True, blank=True, related_name='nact_courses', db_column='Linked_BrachyCourseID')
    
    post_nact_assessment_done = models.BooleanField(default=False, db_column='PostNACT_Assessment_Done')
    post_nact_mri_done = models.BooleanField(default=False, db_column='PostNACT_MRI_Done')
    post_nact_stage = models.CharField(max_length=50, blank=True, null=True, db_column='Post_NACT_Stage')
    notes = models.TextField(blank=True, null=True, db_column='Notes')

    # Approval and locking
    is_approved = models.BooleanField(default=False, db_column='Is_Approved')
    approved_by = models.CharField(max_length=100, blank=True, null=True, db_column='Approved_By')
    approved_on = models.DateTimeField(null=True, blank=True, db_column='Approved_On')
    approval_locked = models.BooleanField(default=False, db_column='Approval_Locked')

    entered_by = models.CharField(max_length=100, blank=True, null=True, db_column='EnteredBy')
    entered_on = models.DateTimeField(default=timezone.now, db_column='EnteredOn')
    soft_deleted = models.BooleanField(default=False, db_column='Soft_Deleted')

    class Meta:
        db_table = 'tblNACTCourse'

    def __str__(self):
        return f"NACT Course ({self.patient.pt_name})"


class NACTCycle(models.Model):
    """Corresponds to tblNACTCycles"""
    nact_cycle_id = models.BigAutoField(primary_key=True, db_column='NACTCycleID')
    course = models.ForeignKey(NACTCourse, on_delete=models.CASCADE, related_name='cycles', db_column='NACTCourseID')
    cycle_number = models.IntegerField(default=1, db_column='Cycle_Number')
    cycle_date = models.DateField(default=date.today, db_column='Cycle_Date')
    cycle_status = models.CharField(max_length=50, blank=True, null=True, default='Administered', db_column='Cycle_Status')
    cycle_toxicity = models.TextField(blank=True, null=True, db_column='Cycle_Toxicity')
    pre_cycle_notes = models.TextField(blank=True, null=True, db_column='Pre_Cycle_Notes')

    class Meta:
        db_table = 'tblNACTCycles'
        ordering = ['cycle_date', 'cycle_number', 'nact_cycle_id']

    def __str__(self):
        return f"NACT Cycle #{self.cycle_number} ({self.cycle_date})"


class NACTDrug(models.Model):
    """Corresponds to tblNACTDrugs"""
    nact_drug_id = models.BigAutoField(primary_key=True, db_column='NACTDrugID')
    cycle = models.ForeignKey(NACTCycle, on_delete=models.CASCADE, related_name='drugs', db_column='NACTCycleID')
    chemo_agent = models.ForeignKey(ChemoAgent, on_delete=models.CASCADE, db_column='ChemoAgentID')
    dose = models.FloatField(null=True, blank=True, db_column='Dose')
    dose_unit = models.ForeignKey(DoseUnit, on_delete=models.SET_NULL, null=True, blank=True, db_column='DoseUnitID')
    no_of_days = models.IntegerField(default=1, db_column='No_Of_Days')
    day_of_administration = models.IntegerField(default=1, db_column='Day_Of_Administration')
    chemo_route = models.ForeignKey(ChemoRoute, on_delete=models.SET_NULL, null=True, blank=True, db_column='ChemoRouteID')
    administered = models.BooleanField(default=True, db_column='Administered')

    class Meta:
        db_table = 'tblNACTDrugs'

    def __str__(self):
        return f"{self.chemo_agent.agent_name} ({self.dose})"


# --- Adjuvant Chemotherapy ---

class AdjuvantChemoCourse(models.Model):
    """Corresponds to tblAdjuvantCourse"""
    adjuvant_course_id = models.BigAutoField(primary_key=True, db_column='AdjuvantCourseID')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='adjuvant_courses', db_column='MR_No')
    course_sequence = models.IntegerField(default=1, db_column='Course_Sequence')
    adjuvant_received = models.BooleanField(default=False, db_column='Adjuvant_Received')
    planned_cycles = models.IntegerField(default=4, db_column='Planned_Cycles')
    received_cycles = models.IntegerField(default=0, db_column='Received_Cycles')
    adjuvant_start_date = models.DateField(null=True, blank=True, db_column='Adjuvant_Start_Date')
    adjuvant_end_date = models.DateField(null=True, blank=True, db_column='Adjuvant_End_Date')
    chemo_status = models.ForeignKey(NACTStatus, on_delete=models.SET_NULL, null=True, blank=True, db_column='ChemoStatusID')
    
    # Backward links to prior definitive treatment
    linked_ebrt_course = models.ForeignKey(EBRTCourse, on_delete=models.SET_NULL, null=True, blank=True, related_name='adjuvant_courses', db_column='Linked_EBRTCourseID')
    linked_brachy_course = models.ForeignKey(BrachyCourse, on_delete=models.SET_NULL, null=True, blank=True, related_name='adjuvant_courses', db_column='Linked_BrachyCourseID')
    
    notes = models.TextField(blank=True, null=True, db_column='Notes')

    # Approval and locking
    is_approved = models.BooleanField(default=False, db_column='Is_Approved')
    approved_by = models.CharField(max_length=100, blank=True, null=True, db_column='Approved_By')
    approved_on = models.DateTimeField(null=True, blank=True, db_column='Approved_On')
    approval_locked = models.BooleanField(default=False, db_column='Approval_Locked')

    entered_by = models.CharField(max_length=100, blank=True, null=True, db_column='EnteredBy')
    entered_on = models.DateTimeField(default=timezone.now, db_column='EnteredOn')
    soft_deleted = models.BooleanField(default=False, db_column='Soft_Deleted')

    class Meta:
        db_table = 'tblAdjuvantCourse'

    def __str__(self):
        return f"Adjuvant Chemo - {self.patient.pt_name}"


class AdjuvantChemoCycle(models.Model):
    """Corresponds to tblAdjuvantCycles"""
    adjuvant_cycle_id = models.BigAutoField(primary_key=True, db_column='AdjuvantCycleID')
    course = models.ForeignKey(AdjuvantChemoCourse, on_delete=models.CASCADE, related_name='cycles', db_column='AdjuvantCourseID')
    cycle_number = models.IntegerField(default=1, db_column='Cycle_Number')
    cycle_date = models.DateField(default=date.today, db_column='Cycle_Date')
    cycle_status = models.CharField(max_length=50, blank=True, null=True, default='Administered', db_column='Cycle_Status')
    cycle_toxicity = models.TextField(blank=True, null=True, db_column='Cycle_Toxicity')
    pre_cycle_notes = models.TextField(blank=True, null=True, db_column='Pre_Cycle_Notes')

    class Meta:
        db_table = 'tblAdjuvantCycles'
        ordering = ['cycle_date', 'cycle_number', 'adjuvant_cycle_id']

    def __str__(self):
        return f"Adjuvant Cycle #{self.cycle_number} ({self.cycle_date})"


class AdjuvantChemoDrug(models.Model):
    """Corresponds to tblAdjuvantDrugs"""
    adjuvant_drug_id = models.BigAutoField(primary_key=True, db_column='AdjuvantDrugID')
    cycle = models.ForeignKey(AdjuvantChemoCycle, on_delete=models.CASCADE, related_name='drugs', db_column='AdjuvantCycleID')
    chemo_agent = models.ForeignKey(ChemoAgent, on_delete=models.CASCADE, db_column='ChemoAgentID')
    dose = models.FloatField(null=True, blank=True, db_column='Dose')
    dose_unit = models.ForeignKey(DoseUnit, on_delete=models.SET_NULL, null=True, blank=True, db_column='DoseUnitID')
    no_of_days = models.IntegerField(default=1, db_column='No_Of_Days')
    day_of_administration = models.IntegerField(default=1, db_column='Day_Of_Administration')
    chemo_route = models.ForeignKey(ChemoRoute, on_delete=models.SET_NULL, null=True, blank=True, db_column='ChemoRouteID')
    administered = models.BooleanField(default=True, db_column='Administered')

    class Meta:
        db_table = 'tblAdjuvantDrugs'

    def __str__(self):
        return f"{self.chemo_agent.agent_name} ({self.dose})"
