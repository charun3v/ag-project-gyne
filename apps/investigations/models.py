from django.db import models
from django.utils import timezone
from datetime import date
from patients.models import Patient

# --- Lookup / Reference Tables for Investigations ---

class ImagingType(models.Model):
    """sbtblImagingType (MRI, CT, PET-CT, USG, X-Ray)"""
    imaging_type_id = models.IntegerField(primary_key=True, db_column='ImagingTypeID')
    imaging_type_name = models.CharField(max_length=100)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblImagingType'
        ordering = ['display_order', 'imaging_type_name']

    def __str__(self):
        return self.imaging_type_name


class ImagingSite(models.Model):
    """sbtblImagingSite (Pelvis, Abdomen, Thorax, Brain)"""
    imaging_site_id = models.IntegerField(primary_key=True, db_column='ImagingSiteID')
    imaging_site_name = models.CharField(max_length=100)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblImagingSite'
        ordering = ['display_order']

    def __str__(self):
        return self.imaging_site_name


class PathSpecimen(models.Model):
    """sbtblPathSpecimen"""
    specimen_id = models.IntegerField(primary_key=True, db_column='PathSpecimenID')
    specimen_name = models.CharField(max_length=150)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblPathSpecimen'
        ordering = ['display_order', 'specimen_name']

    def __str__(self):
        return self.specimen_name


class PathBiopsySite(models.Model):
    """sbtblPathBiopsySite"""
    biopsy_site_id = models.IntegerField(primary_key=True, db_column='PathBiopsySiteID')
    biopsy_site_name = models.CharField(max_length=150)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblPathBiopsySite'
        ordering = ['display_order']

    def __str__(self):
        return self.biopsy_site_name


class FNACSite(models.Model):
    """sbtlbFNACSite"""
    fnac_site_id = models.IntegerField(primary_key=True, db_column='FNACSiteID')
    fnac_site_name = models.CharField(max_length=150)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtlbFNACSite'
        ordering = ['display_order']

    def __str__(self):
        return self.fnac_site_name


class PathType(models.Model):
    """sbtblPathType"""
    path_type_id = models.IntegerField(primary_key=True, db_column='ID')
    path_type_name = models.CharField(max_length=100, db_column='Test_Type_Path')
    display_order = models.IntegerField(default=1, db_column='Dislapy_no')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblPathType'
        ordering = ['display_order']

    def __str__(self):
        return self.path_type_name


class MolecularType(models.Model):
    """sbtblMolecularType"""
    molecular_type_id = models.IntegerField(primary_key=True, db_column='ID')
    test_type_mol = models.CharField(max_length=100, db_column='Test_Type_Mol')
    display_order = models.IntegerField(default=1, db_column='Dislpay__order')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblMolecularType'
        ordering = ['display_order']

    def __str__(self):
        return self.test_type_mol


class MolecularMarker(models.Model):
    """sbtblMolecularMarker (p16, p53, MMR/MSI, PD-L1, BRCA1/2, HER2)"""
    marker_id = models.IntegerField(primary_key=True, db_column='MolecularMarkerID')
    marker_name = models.CharField(max_length=100)
    marker_category = models.CharField(max_length=100, blank=True, null=True)
    result_type = models.CharField(max_length=50, blank=True, null=True)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblMolecularMarker'
        ordering = ['display_order', 'marker_name']

    def __str__(self):
        return self.marker_name


class NodalStation(models.Model):
    """sbtblNodalStation"""
    station_id = models.IntegerField(primary_key=True, db_column='NodalStationID')
    station_name = models.CharField(max_length=150)
    anatomical_group = models.CharField(max_length=100, blank=True, null=True)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblNodalStation'
        ordering = ['display_order', 'station_name']

    def __str__(self):
        return self.station_name


class MRIOrganInvasionStatus(models.Model):
    """sbtblMRIOrganInvasionStatus"""
    status_id = models.IntegerField(primary_key=True, db_column='MRIOrganInvasionStatusID')
    status_name = models.CharField(max_length=100)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'sbtblMRIOrganInvasionStatus'
        ordering = ['display_order']

    def __str__(self):
        return self.status_name


# --- Core Investigation Records ---

class BloodInvestigation(models.Model):
    """Corresponds to tblBlood - Hematology, Biochemistry, Renal & Liver function panels."""
    blood_id = models.BigAutoField(primary_key=True, db_column='BloodID')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='blood_tests', db_column='MR_No')
    test_date = models.DateField(default=date.today, db_column='Test_date')
    lab_reference_no = models.CharField(max_length=100, blank=True, null=True, db_column='Lab_Reference_No')
    specimen_type = models.CharField(max_length=100, default='Blood', db_column='Specimen_Type')
    
    # Complete Blood Count (CBC)
    hb = models.FloatField(null=True, blank=True, db_column='Hb', verbose_name="Hemoglobin (g/dL)")
    tc = models.FloatField(null=True, blank=True, db_column='TC', verbose_name="Total Leukocyte Count (/uL)")
    anc = models.FloatField(null=True, blank=True, db_column='ANC', verbose_name="Absolute Neutrophil Count (/uL)")
    alc = models.FloatField(null=True, blank=True, db_column='ALC', verbose_name="Absolute Lymphocyte Count (/uL)")
    platelet = models.FloatField(null=True, blank=True, db_column='Platelet', verbose_name="Platelet Count (lakhs/uL)")
    
    # Renal Function Test (RFT)
    serum_urea = models.FloatField(null=True, blank=True, db_column='Serum_Urea', verbose_name="Serum Urea (mg/dL)")
    serum_creatinine = models.FloatField(null=True, blank=True, db_column='Serum_Creatinine', verbose_name="Serum Creatinine (mg/dL)")
    
    # Liver Function Test (LFT)
    total_protein = models.FloatField(null=True, blank=True, db_column='Total_Protein', verbose_name="Total Protein (g/dL)")
    serum_albumin = models.FloatField(null=True, blank=True, db_column='Serum_Albumin', verbose_name="Serum Albumin (g/dL)")
    sgot = models.FloatField(null=True, blank=True, db_column='SGOT', verbose_name="SGOT / AST (U/L)")
    sgpt = models.FloatField(null=True, blank=True, db_column='SGPT', verbose_name="SGPT / ALT (U/L)")
    alp = models.FloatField(null=True, blank=True, db_column='ALP', verbose_name="Alkaline Phosphatase (U/L)")
    
    # Electrolytes
    serum_sodium = models.FloatField(null=True, blank=True, db_column='Serum_Sodium', verbose_name="Sodium (mEq/L)")
    serum_potassium = models.FloatField(null=True, blank=True, db_column='Serum_Potassium', verbose_name="Potassium (mEq/L)")
    serum_calcium = models.FloatField(null=True, blank=True, db_column='Serum_Calcium', verbose_name="Calcium (mg/dL)")
    
    details = models.TextField(blank=True, null=True, db_column='Details')
    impression = models.TextField(blank=True, null=True, db_column='Impression')

    # Audit fields
    entered_by = models.CharField(max_length=100, blank=True, null=True, db_column='EnteredBy')
    entered_on = models.DateTimeField(default=timezone.now, db_column='EnteredOn')
    soft_deleted = models.BooleanField(default=False, db_column='Soft_Deleted')

    class Meta:
        db_table = 'tblBlood'
        ordering = ['-test_date', '-blood_id']

    def __str__(self):
        return f"Blood Lab ({self.test_date}) - {self.patient.pt_name}"


class PathologyInvestigation(models.Model):
    """Corresponds to tblPath - Histopathology and Cytology reports."""
    path_id = models.BigAutoField(primary_key=True, db_column='PathID')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='pathology_reports', db_column='MR_No')
    path_date = models.DateField(default=date.today, db_column='Path_Date')
    lab_reference_no = models.CharField(max_length=100, blank=True, null=True, db_column='Lab_Reference_No')
    
    specimen = models.ForeignKey(PathSpecimen, on_delete=models.SET_NULL, null=True, blank=True, db_column='PathSpecimenID')
    biopsy_site = models.ForeignKey(PathBiopsySite, on_delete=models.SET_NULL, null=True, blank=True, db_column='PathBiopsySiteID')
    path_type = models.ForeignKey(PathType, on_delete=models.SET_NULL, null=True, blank=True, db_column='PathTypeID')
    fnac_site = models.ForeignKey(FNACSite, on_delete=models.SET_NULL, null=True, blank=True, db_column='FNACSiteID')
    
    details = models.TextField(blank=True, null=True, db_column='Details')
    impression = models.TextField(blank=True, null=True, db_column='Impression')

    entered_by = models.CharField(max_length=100, blank=True, null=True, db_column='EnteredBy')
    entered_on = models.DateTimeField(default=timezone.now, db_column='EnteredOn')
    last_modified_by = models.CharField(max_length=100, blank=True, null=True, db_column='LastModifiedBy')
    last_modified_on = models.DateTimeField(auto_now=True, db_column='LastModifiedOn')
    soft_deleted = models.BooleanField(default=False, db_column='Soft_Deleted')

    class Meta:
        db_table = 'tblPath'
        ordering = ['-path_date', '-path_id']

    @property
    def site_display(self):
        """Safely returns biopsy site name, FNAC site name, or '-'."""
        if self.biopsy_site and self.biopsy_site.biopsy_site_name:
            return self.biopsy_site.biopsy_site_name
        if self.fnac_site and self.fnac_site.fnac_site_name:
            return self.fnac_site.fnac_site_name
        return "-"

    def __str__(self):
        spec = self.specimen.specimen_name if self.specimen else "Biopsy"
        return f"Pathology: {spec} ({self.path_date}) - {self.patient.pt_name}"


class ImagingInvestigation(models.Model):
    """Corresponds to tblImaging - Radiology investigations."""
    imaging_id = models.BigAutoField(primary_key=True, db_column='ImagingID')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='imaging_studies', db_column='MR_No')
    imaging_date = models.DateField(default=date.today, db_column='Imaging_Date')
    imaging_type = models.ForeignKey(ImagingType, on_delete=models.SET_NULL, null=True, blank=True, db_column='ImagingTypeID')
    imaging_site = models.ForeignKey(ImagingSite, on_delete=models.SET_NULL, null=True, blank=True, db_column='ImagingSiteID')
    lab_reference_no = models.CharField(max_length=100, blank=True, null=True, db_column='Lab_Reference_No')
    other_modality = models.CharField(max_length=100, blank=True, null=True, db_column='Other_Modality')
    
    details = models.TextField(blank=True, null=True, db_column='Details')
    impression = models.TextField(blank=True, null=True, db_column='Impression')

    entered_by = models.CharField(max_length=100, blank=True, null=True, db_column='EnteredBy')
    entered_on = models.DateTimeField(default=timezone.now, db_column='EnteredOn')
    last_modified_by = models.CharField(max_length=100, blank=True, null=True, db_column='LastModifiedBy')
    last_modified_on = models.DateTimeField(auto_now=True, db_column='LastModifiedOn')
    soft_deleted = models.BooleanField(default=False, db_column='Soft_Deleted')

    class Meta:
        db_table = 'tblImaging'
        ordering = ['-imaging_date', '-imaging_id']

    def __str__(self):
        mod = self.imaging_type.imaging_type_name if self.imaging_type else "Scan"
        return f"{mod} ({self.imaging_date}) - {self.patient.pt_name}"


class MRIPelvisDetail(models.Model):
    """Corresponds to tblMRIPelvisDetail - High resolution Pelvic MRI anatomical metrics."""
    mri_detail_id = models.BigAutoField(primary_key=True, db_column='MRIDetailID')
    imaging = models.OneToOneField(ImagingInvestigation, on_delete=models.CASCADE, related_name='pelvis_detail', db_column='ImagingID')
    
    tumour_dimension_1_cm = models.FloatField(null=True, blank=True, db_column='Tumour_Dimension_1_cm')
    tumour_dimension_2_cm = models.FloatField(null=True, blank=True, db_column='Tumour_Dimension_2_cm')
    tumour_dimension_3_cm = models.FloatField(null=True, blank=True, db_column='Tumour_Dimension_3_cm')
    tumour_volume_cc = models.FloatField(null=True, blank=True, db_column='Tumour_Volume_cc')
    
    cervix_involved = models.BooleanField(default=False, db_column='Cervix_Involved')
    cervical_stromal_invasion = models.BooleanField(default=False, db_column='Cervical_Stromal_Invasion')
    cervical_stromal_extent = models.CharField(max_length=100, blank=True, null=True, db_column='Cervical_Stromal_Extent')
    
    parametrium_involved = models.BooleanField(default=False, db_column='Parametrium_Involved')
    para_side = models.CharField(max_length=50, blank=True, null=True, db_column='Para_Side')
    para_left_involved = models.BooleanField(default=False, db_column='Para_Left_Involved')
    para_right_involved = models.BooleanField(default=False, db_column='Para_Right_Involved')
    para_left_extent_cm = models.FloatField(null=True, blank=True, db_column='Para_Left_Extent_cm')
    para_right_extent_cm = models.FloatField(null=True, blank=True, db_column='Para_Right_Extent_cm')
    
    uterine_corpus_involved = models.BooleanField(default=False, db_column='Uterine_Corpus_Involved')
    vaginal_involvement = models.BooleanField(default=False, db_column='Vaginal_Involvement')
    vaginal_extent = models.CharField(max_length=100, blank=True, null=True, db_column='Vaginal_Extent') # Upper third, Middle third, Lower third
    
    bladder_status = models.ForeignKey(MRIOrganInvasionStatus, on_delete=models.SET_NULL, null=True, blank=True, related_name='bladder_mri', db_column='BladderInvasionStatusID')
    rectum_status = models.ForeignKey(MRIOrganInvasionStatus, on_delete=models.SET_NULL, null=True, blank=True, related_name='rectum_mri', db_column='RectumInvasionStatusID')
    
    hydronephrosis_left = models.BooleanField(default=False, db_column='Hydronephrosis_Left')
    hydronephrosis_right = models.BooleanField(default=False, db_column='Hydronephrosis_Right')
    
    nodes_present = models.BooleanField(default=False, db_column='Nodes_Present')
    pelvic_nodes_present = models.BooleanField(default=False, db_column='Pelvic_Nodes_Present')
    pa_nodes_present = models.BooleanField(default=False, db_column='PA_Nodes_Present')
    inguinal_nodes_present = models.BooleanField(default=False, db_column='Inguinal_Nodes_Present')
    
    distant_findings = models.TextField(blank=True, null=True, db_column='Distant_Findings')
    radiologist_impression = models.TextField(blank=True, null=True, db_column='Radiologist_Impression')

    class Meta:
        db_table = 'tblMRIPelvisDetail'

    def __str__(self):
        return f"MRI Pelvis Detail for Imaging #{self.imaging_id}"


class MRINodalStation(models.Model):
    """Corresponds to tblMRINodalStations - Lymph node stations identified on MRI."""
    mri_nodal_id = models.BigAutoField(primary_key=True, db_column='MRINodalID')
    mri_detail = models.ForeignKey(MRIPelvisDetail, on_delete=models.CASCADE, related_name='nodal_stations', db_column='MRIDetailID')
    nodal_station = models.ForeignKey(NodalStation, on_delete=models.CASCADE, db_column='NodalStationID')
    side = models.CharField(max_length=50, blank=True, null=True, db_column='Side') # Left, Right, Bilateral
    number_involved = models.IntegerField(default=1, db_column='Number_Involved')
    largest_size_mm = models.FloatField(null=True, blank=True, db_column='Largest_Size_mm')
    necrosis = models.BooleanField(default=False, db_column='Necrosis')
    notes = models.TextField(blank=True, null=True, db_column='Notes')

    class Meta:
        db_table = 'tblMRINodalStations'

    def __str__(self):
        return f"{self.nodal_station.station_name} ({self.side}) - {self.largest_size_mm}mm"


class MolecularInvestigation(models.Model):
    """Corresponds to tblMolecular - Next-Gen Sequencing, IHC, PCR, biomarkers."""
    molecular_id = models.BigAutoField(primary_key=True, db_column='MolecularID')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='molecular_tests', db_column='MR_No')
    test_date = models.DateField(default=date.today, db_column='Test_Date')
    lab_reference_no = models.CharField(max_length=100, blank=True, null=True, db_column='Lab_Reference_No')
    molecular_type = models.ForeignKey(MolecularType, on_delete=models.SET_NULL, null=True, blank=True, db_column='MolecularTypeID')
    specimen = models.ForeignKey(PathSpecimen, on_delete=models.SET_NULL, null=True, blank=True, db_column='PathSpecimenID')
    specimen_source = models.CharField(max_length=150, blank=True, null=True, db_column='Specimen_Source')
    testing_lab = models.CharField(max_length=150, blank=True, null=True, db_column='Testing_Lab')
    
    details = models.TextField(blank=True, null=True, db_column='Details')
    impression = models.TextField(blank=True, null=True, db_column='Impression')

    entered_by = models.CharField(max_length=100, blank=True, null=True, db_column='EnteredBy')
    entered_on = models.DateTimeField(default=timezone.now, db_column='EnteredOn')
    soft_deleted = models.BooleanField(default=False, db_column='Soft_Deleted')

    class Meta:
        db_table = 'tblMolecular'
        ordering = ['-test_date', '-molecular_id']

    def __str__(self):
        return f"Molecular ({self.test_date}) - {self.patient.pt_name}"


class MolecularResult(models.Model):
    """Corresponds to tblMolecularResults - Specific biomarker outcomes."""
    result_id = models.BigAutoField(primary_key=True, db_column='ResultID')
    molecular = models.ForeignKey(MolecularInvestigation, on_delete=models.CASCADE, related_name='results', db_column='MolecularID')
    marker = models.ForeignKey(MolecularMarker, on_delete=models.CASCADE, db_column='MolecularMarkerID')
    result_value = models.CharField(max_length=150, blank=True, null=True, db_column='Result_Value')
    result_numeric = models.FloatField(null=True, blank=True, db_column='Result_Numeric')
    result_status = models.CharField(max_length=50, blank=True, null=True, db_column='Result_Status')
    notes = models.CharField(max_length=255, blank=True, null=True, db_column='Notes')

    class Meta:
        db_table = 'tblMolecularResults'

    def __str__(self):
        return f"{self.marker.marker_name}: {self.result_value}"
