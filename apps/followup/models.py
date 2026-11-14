from django.db import models
from django.utils import timezone
from datetime import date
from patients.models import Patient
from clinical.models import Encounter
from systemic.models import ResponseStatus

# --- Lookup / Reference Tables for Follow-Up ---

class DiseaseStatus(models.Model):
    """sbtblDiseaseStatus (No Evidence of Disease, Stable, Partial Response, Progression)"""
    disease_status_id = models.IntegerField(primary_key=True, db_column='DiseaseStatusID')
    status_name = models.CharField(max_length=100)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblDiseaseStatus'
        ordering = ['display_order']

    def __str__(self):
        return self.status_name


class FollowUpContactType(models.Model):
    """sbtblFollowUpContactType (In-person Clinic, Telephone, Video consult, Proxy)"""
    contact_type_id = models.IntegerField(primary_key=True, db_column='FollowUpContactTypeID')
    contact_type = models.CharField(max_length=100)
    is_proxy = models.BooleanField(default=False)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblFollowUpContactType'
        ordering = ['display_order']

    def __str__(self):
        return self.contact_type


class ProxyStatus(models.Model):
    """sbtblProxyStatus"""
    proxy_status_id = models.IntegerField(primary_key=True, db_column='ProxyStatusID')
    status_name = models.CharField(max_length=100)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblProxyStatus'
        ordering = ['display_order']

    def __str__(self):
        return self.status_name


class RecurrenceSite(models.Model):
    """sbtblRecurrenceSite (Vault / Local, Pelvic Nodal, Para-aortic, Distant Visceral)"""
    recurrence_site_id = models.IntegerField(primary_key=True, db_column='RecurrenceSiteID')
    site_name = models.CharField(max_length=100)
    site_category = models.CharField(max_length=100, blank=True, null=True)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblRecurrenceSite'
        ordering = ['display_order']

    def __str__(self):
        return self.site_name


class CauseOfDeath(models.Model):
    """sbtblCauseOfDeath"""
    cause_of_death_id = models.IntegerField(primary_key=True, db_column='CauseOfDeathID')
    cause_name = models.CharField(max_length=150)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblCauseOfDeath'
        ordering = ['display_order']

    def __str__(self):
        return self.cause_name


# --- Follow-Up Tracking ---

class FollowUpStatus(models.Model):
    """Corresponds to tblFollowUpStatus - Longitudinal survival, recurrence, and performance monitoring."""
    follow_up_status_id = models.BigAutoField(primary_key=True, db_column='FollowUpStatusID')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='follow_up_records', db_column='MR_No')
    encounter = models.ForeignKey(Encounter, on_delete=models.SET_NULL, null=True, blank=True, db_column='EncounterID', related_name='followup_records')
    follow_up_date = models.DateField(default=date.today, db_column='FollowUp_Date')
    
    contact_type = models.ForeignKey(FollowUpContactType, on_delete=models.SET_NULL, null=True, blank=True, db_column='FollowUpContactTypeID')
    proxy_status = models.ForeignKey(ProxyStatus, on_delete=models.SET_NULL, null=True, blank=True, db_column='ProxyStatusID')
    
    disease_status = models.ForeignKey(DiseaseStatus, on_delete=models.SET_NULL, null=True, blank=True, db_column='DiseaseStatusID')
    response_status = models.ForeignKey(ResponseStatus, on_delete=models.SET_NULL, null=True, blank=True, db_column='ResponseID')
    
    # Recurrence monitoring
    recurrence_detected = models.BooleanField(default=False, db_column='Recurrence_Detected')
    date_of_recurrence = models.DateField(null=True, blank=True, db_column='Date_Of_Recurrence')
    recurrence_confirmed_by = models.CharField(max_length=150, blank=True, null=True, db_column='Recurrence_Confirmed_By')
    
    recurrence_local = models.BooleanField(default=False, db_column='Recurrence_Local')
    recurrence_nodal = models.BooleanField(default=False, db_column='Recurrence_Nodal')
    recurrence_distant = models.BooleanField(default=False, db_column='Recurrence_Distant')
    second_primary = models.BooleanField(default=False, db_column='Second_Primary')
    
    node_pelvic = models.BooleanField(default=False, db_column='Node_Pelvic')
    node_para_aortic = models.BooleanField(default=False, db_column='Node_ParaAortic')
    node_inguinal = models.BooleanField(default=False, db_column='Node_Inguinal')
    distant_nodal_other = models.BooleanField(default=False, db_column='Distant_Nodal_Other')
    distant_visceral = models.BooleanField(default=False, db_column='Distant_Visceral')
    
    recurrence_site = models.ForeignKey(RecurrenceSite, on_delete=models.SET_NULL, null=True, blank=True, db_column='RecurrenceSiteID')
    recurrence_sites = models.ManyToManyField(RecurrenceSite, blank=True, related_name='followup_records', db_table='tblFollowUpRecurrenceSites')
    recurrence_treatment_plan = models.TextField(blank=True, null=True, db_column='Recurrence_Treatment_Plan')
    
    # Survival & Death Monitoring
    death_reported = models.BooleanField(default=False, db_column='Death_Reported')
    date_of_death = models.DateField(null=True, blank=True, db_column='Date_Of_Death')
    cause_of_death = models.ForeignKey(CauseOfDeath, on_delete=models.SET_NULL, null=True, blank=True, db_column='CauseOfDeathID')
    
    performance_notes = models.TextField(blank=True, null=True, db_column='Performance_Notes')
    next_fu_date = models.DateField(null=True, blank=True, db_column='Next_FU_Date')
    next_fu_notes = models.CharField(max_length=255, blank=True, null=True, db_column='Next_FU_Notes')

    entered_by = models.CharField(max_length=100, blank=True, null=True, db_column='EnteredBy')
    entered_on = models.DateTimeField(default=timezone.now, db_column='EnteredOn')
    last_modified_by = models.CharField(max_length=100, blank=True, null=True, db_column='LastModifiedBy')
    last_modified_on = models.DateTimeField(auto_now=True, db_column='LastModifiedOn')
    soft_deleted = models.BooleanField(default=False, db_column='Soft_Deleted')

    class Meta:
        db_table = 'tblFollowUpStatus'
        ordering = ['-follow_up_date', '-follow_up_status_id']

    def __str__(self):
        status_str = self.disease_status.status_name if self.disease_status else "Status"
        return f"Follow-up ({self.follow_up_date}) - {self.patient.pt_name}: {status_str}"

    @property
    def recurrence_sites_display(self):
        sites = list(self.recurrence_sites.all())
        if sites:
            return ", ".join([s.site_name for s in sites])
        if self.recurrence_site:
            return self.recurrence_site.site_name
        return ""


class FollowUpInvestigationLink(models.Model):
    """Corresponds to tblFollowUpInvestigationLink"""
    link_id = models.BigAutoField(primary_key=True, db_column='FollowUpInvestigationLinkID')
    follow_up = models.ForeignKey(FollowUpStatus, on_delete=models.CASCADE, related_name='investigation_links', db_column='FollowUpStatusID')
    investigation_type = models.CharField(max_length=50, db_column='InvestigationType') # Blood, Imaging, Pathology, Molecular
    investigation_id = models.IntegerField(db_column='InvestigationID')

    class Meta:
        db_table = 'tblFollowUpInvestigationLink'
