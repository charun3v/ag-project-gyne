import json
import os
from pathlib import Path
from datetime import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction

from core.models import Role, UserProfile, State, District, Consultant, AuditLog, AppSetting
from patients.models import Patient
from clinical.models import (
    PrimarySite, Histology, Grade, StagingSystem, BasisOfDiagnosis, ECOGScore,
    EncounterType, SVGRegion, Encounter, ClinicalSVGFinding, ClinicalHistory, Diagnosis
)
from investigations.models import (
    ImagingType, ImagingSite, PathSpecimen, PathBiopsySite, FNACSite, PathType,
    MolecularType, MolecularMarker, NodalStation, MRIOrganInvasionStatus,
    BloodInvestigation, PathologyInvestigation, ImagingInvestigation, MRIPelvisDetail,
    MRINodalStation, MolecularInvestigation, MolecularResult
)
from radiotherapy.models import (
    EBRTIntent, EBRTTechnique, EBRTSite, TreatmentCentre, RTMachine, InterruptionReason,
    TreatmentCourseStatus, BrachySourceType, BrachyDosing, BrachyApplicator,
    BrachyImageGuidance, AnaesthesiaType, BrachySessionStatus, BrachyFractionStatus,
    BrachyISTemplate, EBRTCourse, EBRTCourseSite, EBRTInterruption,
    BrachyCourse, BrachySession, BrachyFraction
)
from systemic.models import (
    ChemoAgent, ChemoRegimen, ChemoRoute, DoseUnit, NACTStatus, ResponseStatus,
    ConcurrentChemoCourse, ConcurrentChemoCycle, ConcurrentChemoDrug,
    NACTCourse, NACTCycle, NACTDrug, AdjuvantChemoCourse
)
from followup.models import (
    DiseaseStatus, FollowUpContactType, ProxyStatus, RecurrenceSite, CauseOfDeath,
    FollowUpStatus
)

DATA_DIR = Path(r"C:\Users\charu\.gemini\antigravity\brain\b8e45166-3048-41ed-8781-3858a4ef253b\scratch\table_data")

def load_json(table_name):
    p = DATA_DIR / f"{table_name}.json"
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return [data]
    return data

def parse_date(val):
    if not val:
        return None
    try:
        if isinstance(val, str):
            val = val.strip()
            if ' ' in val:
                return datetime.strptime(val.split(' ')[0], "%Y-%m-%d").date()
            return datetime.strptime(val, "%Y-%m-%d").date()
    except Exception:
        pass
    return None

def parse_datetime(val):
    if not val:
        return None
    try:
        if isinstance(val, str):
            return datetime.strptime(val.strip(), "%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return None

class Command(BaseCommand):
    help = "Imports MS Access data from exported JSON tables into Django models"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting MS Access data migration..."))

        # 1. Core Lookups
        self.stdout.write("1/7 Importing Core Lookups...")
        for row in load_json("sbtblRole"):
            Role.objects.update_or_create(
                role_id=row["RoleID"],
                defaults={
                    "role_name": row["Role_Name"],
                    "role_description": row.get("Role_Description"),
                    "display_order": row.get("Display_Order", 1) or 1,
                    "is_active": bool(row.get("IsActive", True)),
                    "cap_login": bool(row.get("Cap_Login", True)),
                    "cap_view_patients": bool(row.get("Cap_ViewPatients", True)),
                    "cap_register_patient": bool(row.get("Cap_RegisterPatient", False)),
                    "cap_edit_demographics": bool(row.get("Cap_EditDemographics", False)),
                    "cap_enter_clinical": bool(row.get("Cap_EnterClinical", False)),
                    "cap_enter_investigations": bool(row.get("Cap_EnterInvestigations", False)),
                    "cap_enter_treatment": bool(row.get("Cap_EnterTreatment", False)),
                    "cap_enter_dosimetry": bool(row.get("Cap_EnterDosimetry", False)),
                    "cap_enter_followup": bool(row.get("Cap_EnterFollowUp", False)),
                    "cap_approve": bool(row.get("Cap_Approve", False)),
                    "cap_unlock_approved": bool(row.get("Cap_UnlockApproved", False)),
                    "cap_delete_records": bool(row.get("Cap_DeleteRecords", False)),
                    "cap_manage_users": bool(row.get("Cap_ManageUsers", False)),
                    "cap_manage_roles": bool(row.get("Cap_ManageRoles", False)),
                    "cap_view_reports": bool(row.get("Cap_ViewReports", True)),
                    "cap_export_data": bool(row.get("Cap_ExportData", False)),
                }
            )

        for row in load_json("tblStates"):
            State.objects.update_or_create(
                state_id=row["StateID"],
                defaults={"state_name": row["StateName"]}
            )

        for row in load_json("tblDistricts"):
            st_id = row.get("StateID")
            District.objects.update_or_create(
                district_id=row["DistrictID"],
                defaults={
                    "district_name": row["DistrictName"],
                    "state_id": st_id if State.objects.filter(state_id=st_id).exists() else 1
                }
            )

        for row in load_json("tblConsultant"):
            Consultant.objects.update_or_create(
                consultant_id=row["ConsultantID"],
                defaults={
                    "consultant_name": row["Consultant_Name"],
                    "display_order": row.get("Display_Order", 1) or 1,
                    "is_active": bool(row.get("IsActive", True))
                }
            )

        for row in load_json("tblAppSettings"):
            AppSetting.objects.update_or_create(
                setting_key=row["Setting_Key"],
                defaults={"setting_value": row.get("Setting_Value")}
            )

        # 2. Clinical Lookups
        self.stdout.write("2/7 Importing Clinical Lookups...")
        for row in load_json("sbtblPrimarysite"):
            PrimarySite.objects.update_or_create(site_id=row["PrimarySiteID"], defaults={"site": row["Site"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblHistology"):
            Histology.objects.update_or_create(histology_id=row["HistologyID"], defaults={"histology_name": row["Histology_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblGrade"):
            Grade.objects.update_or_create(grade_id=row["GradeID"], defaults={"grade_name": row["Grade_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblStagingSystem"):
            StagingSystem.objects.update_or_create(staging_system_id=row["StagingSystemID"], defaults={"system_name": row["System_Name"], "system_version": row.get("System_Version"), "applies_to_disease": row.get("Applies_To_Disease"), "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblBasisOfDiagnosis"):
            BasisOfDiagnosis.objects.update_or_create(basis_id=row["BasisID"], defaults={"basis_name": row["Basis_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblECOG"):
            ECOGScore.objects.update_or_create(ecog_id=row["ECOGID"], defaults={"score": row["Score"], "description": row.get("Description", ""), "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblEncounterType"):
            EncounterType.objects.update_or_create(encounter_type_id=row["EncounterTypeID"], defaults={"encounter_type_name": row["EncounterType_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblSVGRegions"):
            SVGRegion.objects.update_or_create(svg_region_id=row["SVGRegionID"], defaults={"region_code": row["Region_Code"], "display_label": row.get("Display_Label", row["Region_Code"]), "view_name": row.get("View_Name"), "organ": row.get("Organ"), "position": row.get("Position"), "anatomical_group": row.get("Anatomical_Group"), "default_color": row.get("Default_Color"), "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})

        # 3. Investigation Lookups
        self.stdout.write("3/7 Importing Investigation Lookups...")
        for row in load_json("sbtblImagingType"):
            ImagingType.objects.update_or_create(imaging_type_id=row["ImagingTypeID"], defaults={"imaging_type_name": row["ImagingType_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblImagingSite"):
            ImagingSite.objects.update_or_create(imaging_site_id=row["ImagingSiteID"], defaults={"imaging_site_name": row["ImagingSite_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblPathSpecimen"):
            PathSpecimen.objects.update_or_create(specimen_id=row["PathSpecimenID"], defaults={"specimen_name": row["Specimen_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblPathBiopsySite"):
            PathBiopsySite.objects.update_or_create(biopsy_site_id=row["PathBiopsySiteID"], defaults={"biopsy_site_name": row["BiopsySite_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtlbFNACSite"):
            FNACSite.objects.update_or_create(fnac_site_id=row["FNACSiteID"], defaults={"fnac_site_name": row.get("FNAC_Site", row.get("FNACSite_Name")), "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblPathType"):
            PathType.objects.update_or_create(path_type_id=row["ID"], defaults={"path_type_name": row["Test_Type_Path"], "display_order": row.get("Dislapy_no", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblMolecularType"):
            MolecularType.objects.update_or_create(molecular_type_id=row["ID"], defaults={"test_type_mol": row["Test_Type_Mol"], "display_order": row.get("Dislpay__order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblMolecularMarker"):
            MolecularMarker.objects.update_or_create(marker_id=row["MolecularMarkerID"], defaults={"marker_name": row["Marker_Name"], "marker_category": row.get("Marker_Category"), "result_type": row.get("Result_Type"), "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblNodalStation"):
            NodalStation.objects.update_or_create(station_id=row["NodalStationID"], defaults={"station_name": row["Station_Name"], "anatomical_group": row.get("Anatomical_Group"), "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblMRIOrganInvasionStatus"):
            MRIOrganInvasionStatus.objects.update_or_create(status_id=row["MRIOrganInvasionStatusID"], defaults={"status_name": row["Status_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})

        # 4. Radiotherapy & Systemic Lookups
        self.stdout.write("4/7 Importing Treatment Lookups...")
        for row in load_json("sbtblEBRTIntent"):
            EBRTIntent.objects.update_or_create(intent_id=row["EBRTIntentID"], defaults={"intent_name": row["Intent_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblEBRTechnique"):
            EBRTTechnique.objects.update_or_create(technique_id=row["RTTechniqueID"], defaults={"technique_name": row["Technique_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblEBRTSite"):
            EBRTSite.objects.update_or_create(site_id=row["EBRTSiteID"], defaults={"site_name": row["Site_Name"], "site_category": row.get("Site_Category"), "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblTreatmentCentre"):
            TreatmentCentre.objects.update_or_create(centre_id=row["TreatmentCentreID"], defaults={"centre_code": row["Centre_Code"], "centre_name": row.get("Centre_Name", row["Centre_Code"]), "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblRTMachine"):
            RTMachine.objects.update_or_create(machine_id=row["RTMachineID"], defaults={"machine_name": row["Machine_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblInterruptionReason"):
            InterruptionReason.objects.update_or_create(reason_id=row["InterruptionReasonID"], defaults={"reason_name": row["Reason_Name"], "allow_custom_text": bool(row.get("Allow_Custom_Text", False)), "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblTreatmentCourseStatus"):
            TreatmentCourseStatus.objects.update_or_create(course_status_id=row["CourseStatusID"], defaults={"status_name": row["Status_Name"], "is_terminal": bool(row.get("IsTerminal", False)), "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblBrachySourceType"):
            BrachySourceType.objects.update_or_create(source_id=row["BrachySourceID"], defaults={"source_name": row["Source_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblBrachyDosing"):
            BrachyDosing.objects.update_or_create(dosing_id=row["BrachyDosingID"], defaults={"dosing_point": row["Dosing_Point"], "dosing_system": row.get("Dosing_System"), "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblBrachyApplicator"):
            BrachyApplicator.objects.update_or_create(applicator_id=row["BrachyApplicatorID"], defaults={"applicator_name": row["Applicator_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblBrachyImageGuidance"):
            BrachyImageGuidance.objects.update_or_create(guidance_id=row["BrachyImageGuidanceID"], defaults={"guidance_name": row["ImageGuidance_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblAnaesthesiaType"):
            AnaesthesiaType.objects.update_or_create(anaesthesia_id=row["AnaesthesiaTypeID"], defaults={"anaesthesia_name": row["Anaesthesia_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblBrachySessionStatus"):
            BrachySessionStatus.objects.update_or_create(status_id=row["BrachySessionStatusID"], defaults={"status_name": row["Status_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblBrachyFractionStatus"):
            BrachyFractionStatus.objects.update_or_create(status_id=row["BrachyFractionStatusID"], defaults={"status_name": row["Status_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblBrachyISTemplate"):
            BrachyISTemplate.objects.update_or_create(template_id=row["ID"], defaults={"template_name": row["IS_Template_name"], "display_order": row.get("DislayOrder", 1) or 1, "is_active": bool(row.get("IsActive", True))})

        # Chemotherapy
        for row in load_json("sbtblChemoAgent"):
            ChemoAgent.objects.update_or_create(agent_id=row["ChemoAgentID"], defaults={"agent_name": row["Agent_Name"], "agent_class": row.get("Agent_Class"), "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblChemoRegimen"):
            ChemoRegimen.objects.update_or_create(regimen_id=row["ChemoRegimenID"], defaults={"regimen_code": row["Regimen_Code"], "regimen_description": row["Regimen_Description"], "typical_indication": row.get("Typical_Indication"), "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblChemoRoute"):
            ChemoRoute.objects.update_or_create(route_id=row["ChemoRouteID"], defaults={"route_name": row["Route_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblDoseUnit"):
            DoseUnit.objects.update_or_create(unit_id=row["DoseUnitID"], defaults={"unit_name": row["Unit_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblNACTStatus"):
            NACTStatus.objects.update_or_create(status_id=row["NACTStatusID"], defaults={"status_name": row["Status_Name"], "is_terminal": bool(row.get("IsTerminal", False)), "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblResponseStatus"):
            ResponseStatus.objects.update_or_create(response_id=row["ResponseID"], defaults={"response_code": row["Response_Code"], "response_description": row["Response_Description"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})

        # Follow-Up Lookups
        for row in load_json("sbtblDiseaseStatus"):
            DiseaseStatus.objects.update_or_create(disease_status_id=row["DiseaseStatusID"], defaults={"status_name": row["Status_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblFollowUpContactType"):
            FollowUpContactType.objects.update_or_create(contact_type_id=row["FollowUpContactTypeID"], defaults={"contact_type": row["Contact_Type"], "is_proxy": bool(row.get("Is_Proxy", False)), "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblProxyStatus"):
            ProxyStatus.objects.update_or_create(proxy_status_id=row["ProxyStatusID"], defaults={"status_name": row["Status_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblRecurrenceSite"):
            RecurrenceSite.objects.update_or_create(recurrence_site_id=row["RecurrenceSiteID"], defaults={"site_name": row["Site_Name"], "site_category": row.get("Site_Category"), "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})
        for row in load_json("sbtblCauseOfDeath"):
            CauseOfDeath.objects.update_or_create(cause_of_death_id=row["CauseOfDeathID"], defaults={"cause_name": row["Cause_Name"], "display_order": row.get("Display_Order", 1) or 1, "is_active": bool(row.get("IsActive", True))})

        # 5. User Accounts
        self.stdout.write("5/7 Importing Users...")
        for row in load_json("tblUsers"):
            uname = row["Users"].strip()
            user, created = User.objects.get_or_create(
                username=uname,
                defaults={
                    "first_name": row.get("FullName", "") or "",
                    "is_active": bool(row.get("isActive", True)),
                    "is_staff": True,
                    "is_superuser": uname.lower() in ("admin", "administrator"),
                }
            )
            if created:
                user.set_password("Admin@123")
                user.save()

            role_obj = Role.objects.filter(role_id=row.get("RoleID")).first() if row.get("RoleID") else None
            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    "role": role_obj,
                    "user_level": row.get("UserLevel"),
                }
            )

        # 6. Patients
        self.stdout.write("6/7 Importing Patients...")
        for row in load_json("tblPtDetails"):
            st_id = row.get("StateID")
            dist_id = row.get("DistrictID")
            cons_id = row.get("Primary_ConsultantID")
            
            Patient.objects.update_or_create(
                mr_no=row["MR_No"],
                defaults={
                    "pt_name": row["Pt_name"],
                    "sex": row.get("Sex", "Female"),
                    "date_of_birth": parse_date(row.get("Date_Of_birth")),
                    "dob_is_estimated": bool(row.get("DOB_Is_Estimated", False)),
                    "date_of_registration": parse_date(row.get("Date_of_registration")) or date.today(),
                    "phone": row.get("Phone", ""),
                    "phone_alternate": row.get("Phone_Alternate"),
                    "address": row.get("Address"),
                    "state_id": st_id if State.objects.filter(state_id=st_id).exists() else None,
                    "district_id": dist_id if District.objects.filter(district_id=dist_id).exists() else None,
                    "pincode": row.get("Pincode"),
                    "digipin": row.get("Digipin"),
                    "country": row.get("Country", "India"),
                    "primary_consultant_id": cons_id if Consultant.objects.filter(consultant_id=cons_id).exists() else None,
                    "notes": row.get("Notes"),
                    "entered_by": row.get("EnteredBy"),
                    "entered_on": parse_datetime(row.get("EnteredOn")) or timezone.now(),
                    "soft_deleted": bool(row.get("Soft_Deleted", False)),
                }
            )

        # 7. Clinical Records
        self.stdout.write("7/7 Importing Clinical Records & Treatments...")
        
        # Clinical Encounters
        for row in load_json("tblEncounter"):
            p_mr = row.get("MR_No")
            if not Patient.objects.filter(mr_no=p_mr).exists():
                continue
            enc_type_id = row.get("EncounterTypeID")
            ecog_id = row.get("ECOG")

            Encounter.objects.update_or_create(
                clinical_id=row["ClinicalID"],
                defaults={
                    "patient_id": p_mr,
                    "encounter_type_id": enc_type_id if EncounterType.objects.filter(encounter_type_id=enc_type_id).exists() else None,
                    "encounter_date": parse_date(row.get("Encounter_Date")) or date.today(),
                    "height": row.get("Height"),
                    "weight": row.get("Weight"),
                    "ecog_id": ecog_id if ECOGScore.objects.filter(ecog_id=ecog_id).exists() else None,
                    "presenting_complaints": row.get("Presenting_Complaints"),
                    "examination_findings": row.get("Examination_Findings"),
                    "prev_tx_history": row.get("Prev_Tx_History"),
                    "parametrial_invasion": bool(row.get("Parametrial_Invasion", False)),
                    "para_left": bool(row.get("Para_Left", False)),
                    "para_right": bool(row.get("Para_Right", False)),
                    "para_extent_left_cm": row.get("Para_Extent_Left_cm"),
                    "para_extent_right_cm": row.get("Para_Extent_Right_cm"),
                    "rectal_invasion": bool(row.get("Rectal_Invasion", False)),
                    "bladder_invasion": bool(row.get("Bladder_Invasion", False)),
                    "tumour_size_cm": row.get("Tumour_Size_cm"),
                    "tumour_size_2_cm": row.get("Tumour_Size_2_cm"),
                    "ebrt_given": bool(row.get("EBRT_Given", False)),
                    "linked_ebrt_course_id": row.get("Linked_EBRTCourseID"),
                    "tandem_sounded": bool(row.get("Tandem_Sounded", False)),
                    "tandem_length_cm": row.get("Tandem_Length_cm"),
                    "findings_approved_by": row.get("Findings_Approved_By"),
                    "findings_approved_on": parse_datetime(row.get("Findings_Approved_On")),
                    "findings_locked": bool(row.get("Findings_Locked", False)),
                    "svg_approved_by": row.get("SVG_Approved_By"),
                    "svg_approved_on": parse_datetime(row.get("SVG_Approved_On")),
                    "svg_locked": bool(row.get("SVG_Locked", False)),
                    "entered_by": row.get("EnteredBy"),
                    "entered_on": parse_datetime(row.get("EnteredOn")) or timezone.now(),
                    "soft_deleted": bool(row.get("Soft_Deleted", False)),
                }
            )

        # Clinical SVG Findings
        for row in load_json("tblClinicalSVGFindings"):
            enc_id = row.get("EncounterID")
            reg_id = row.get("SVGRegionID")
            if not Encounter.objects.filter(clinical_id=enc_id).exists() or not SVGRegion.objects.filter(svg_region_id=reg_id).exists():
                continue
            ClinicalSVGFinding.objects.update_or_create(
                svg_finding_id=row["SVGFindingID"],
                defaults={
                    "encounter_id": enc_id,
                    "region_id": reg_id,
                    "involvement_type": row.get("Involvement_Type"),
                    "lesion_type": row.get("Lesion_Type"),
                    "depth_of_invasion": row.get("Depth_Of_Invasion"),
                    "bleeds_on_touch": bool(row.get("Bleeds_On_Touch", False)),
                    "necrotic": bool(row.get("Necrotic", False)),
                    "region_notes": row.get("Region_Notes"),
                    "entered_by": row.get("EnteredBy"),
                    "entered_on": parse_datetime(row.get("EnteredOn")) or timezone.now(),
                    "soft_deleted": bool(row.get("Soft_Deleted", False)),
                    "approved_by": row.get("Approved_By"),
                    "approved_on": parse_datetime(row.get("Approved_On")),
                    "approval_locked": bool(row.get("Approval_Locked", False)),
                }
            )

        # History
        for row in load_json("tblHistory"):
            p_mr = row.get("MR_No")
            if not Patient.objects.filter(mr_no=p_mr).exists():
                continue
            ClinicalHistory.objects.update_or_create(
                history_id=row["HistoryID"],
                defaults={
                    "patient_id": p_mr,
                    "snapshot_date": parse_date(row.get("Snapshot_Date")) or date.today(),
                    "hpi": row.get("HPI"),
                    "past_med_surg": row.get("Past_Med_Surg"),
                    "hypertension": bool(row.get("Hypertension", False)),
                    "hypothyroidism": bool(row.get("Hypothyroidism", False)),
                    "seizures": bool(row.get("Seizures", False)),
                    "diabetic": bool(row.get("Diabetic", False)),
                    "comorbidity_others": bool(row.get("Comorbidity_Others", False)),
                    "comorbidity_notes": row.get("Comorbidity_Notes"),
                    "smoking": bool(row.get("Smoking", False)),
                    "alcohol": bool(row.get("Alcohol", False)),
                    "tobacco_chewing": bool(row.get("Tobacco_Chewing", False)),
                    "habits_others": bool(row.get("Habits_Others", False)),
                    "habits_notes": row.get("Habits_Notes"),
                    "bleeding_pv": bool(row.get("Bleeding_PV", False)),
                    "water_discharge_pv": bool(row.get("Water_Discharge_PV", False)),
                    "dyspareunia": bool(row.get("Dyspareunia", False)),
                    "loin_pain": bool(row.get("Loin_Pain", False)),
                    "prior_radiation": bool(row.get("Prior_Radiation", False)),
                    "prior_radiation_details": row.get("Prior_Radiation_Details"),
                    "previous_surgery": bool(row.get("Previous_Surgery", False)),
                    "previous_surgery_details": row.get("Previous_Surgery_Details"),
                    "entered_by": row.get("EnteredBy"),
                    "entered_on": parse_datetime(row.get("EnteredOn")) or timezone.now(),
                    "soft_deleted": bool(row.get("Soft_Deleted", False)),
                }
            )

        # Diagnosis
        for row in load_json("tblDiagnosis"):
            p_mr = row.get("MR_No")
            if not Patient.objects.filter(mr_no=p_mr).exists():
                continue
            Diagnosis.objects.update_or_create(
                diagnosis_id=row["DiagnosisID"],
                defaults={
                    "patient_id": p_mr,
                    "diagnosis_sequence": row.get("Diagnosis_Sequence", 1) or 1,
                    "date_of_diagnosis": parse_date(row.get("Date_Of_Diagnosis")) or date.today(),
                    "primary_site_id": row.get("PrimarySiteID"),
                    "diagnosis_description": row.get("Diagnosis_Description"),
                    "histology_id": row.get("HistologyID"),
                    "histology_other": row.get("Histology_Other"),
                    "grade_id": row.get("GradeID"),
                    "basis_id": row.get("BasisID"),
                    "staging_system_id": row.get("StagingSystemID"),
                    "stage_text": row.get("Stage_Text"),
                    "t_status": row.get("T_Status"),
                    "n_status": row.get("N_Status"),
                    "m_status": row.get("M_Status"),
                    "laterality": row.get("Laterality"),
                    "pathology_text": row.get("Pathology_Text"),
                    "comments": row.get("Comments"),
                    "is_current": bool(row.get("Is_Current", True)),
                    "entered_by": row.get("EnteredBy"),
                    "entered_on": parse_datetime(row.get("EnteredOn")) or timezone.now(),
                    "soft_deleted": bool(row.get("Soft_Deleted", False)),
                }
            )

        # Blood Investigations
        for row in load_json("tblBlood"):
            p_mr = row.get("MR_No")
            if not Patient.objects.filter(mr_no=p_mr).exists():
                continue
            BloodInvestigation.objects.update_or_create(
                blood_id=row["BloodID"],
                defaults={
                    "patient_id": p_mr,
                    "test_date": parse_date(row.get("Test_date")) or date.today(),
                    "lab_reference_no": row.get("Lab_Reference_No"),
                    "specimen_type": row.get("Specimen_Type", "Blood"),
                    "hb": row.get("Hb"),
                    "tc": row.get("TC"),
                    "anc": row.get("ANC"),
                    "alc": row.get("ALC"),
                    "platelet": row.get("Platelet"),
                    "serum_urea": row.get("Serum_Urea"),
                    "serum_creatinine": row.get("Serum_Creatinine"),
                    "total_protein": row.get("Total_Protein"),
                    "serum_albumin": row.get("Serum_Albumin"),
                    "sgot": row.get("SGOT"),
                    "sgpt": row.get("SGPT"),
                    "alp": row.get("ALP"),
                    "serum_sodium": row.get("Serum_Sodium"),
                    "serum_potassium": row.get("Serum_Potassium"),
                    "serum_calcium": row.get("Serum_Calcium"),
                    "details": row.get("Details"),
                    "impression": row.get("Impression"),
                    "entered_by": row.get("EnteredBy"),
                    "entered_on": parse_datetime(row.get("EnteredOn")) or timezone.now(),
                    "soft_deleted": bool(row.get("Soft_Deleted", False)),
                }
            )

        # Pathology
        for row in load_json("tblPath"):
            p_mr = row.get("MR_No")
            if not Patient.objects.filter(mr_no=p_mr).exists():
                continue
            PathologyInvestigation.objects.update_or_create(
                path_id=row["PathID"],
                defaults={
                    "patient_id": p_mr,
                    "path_date": parse_date(row.get("Path_Date")) or date.today(),
                    "lab_reference_no": row.get("Lab_Reference_No"),
                    "specimen_id": row.get("PathSpecimenID"),
                    "biopsy_site_id": row.get("PathBiopsySiteID"),
                    "path_type_id": row.get("PathTypeID"),
                    "fnac_site_id": row.get("FNACSiteID"),
                    "details": row.get("Details"),
                    "impression": row.get("Impression"),
                    "entered_by": row.get("EnteredBy"),
                    "entered_on": parse_datetime(row.get("EnteredOn")) or timezone.now(),
                    "soft_deleted": bool(row.get("Soft_Deleted", False)),
                }
            )

        # Imaging & MRI Pelvis Detail
        for row in load_json("tblImaging"):
            p_mr = row.get("MR_No")
            if not Patient.objects.filter(mr_no=p_mr).exists():
                continue
            ImagingInvestigation.objects.update_or_create(
                imaging_id=row["ImagingID"],
                defaults={
                    "patient_id": p_mr,
                    "imaging_date": parse_date(row.get("Imaging_Date")) or date.today(),
                    "imaging_type_id": row.get("ImagingTypeID"),
                    "imaging_site_id": row.get("ImagingSiteID"),
                    "lab_reference_no": row.get("Lab_Reference_No"),
                    "other_modality": row.get("Other_Modality"),
                    "details": row.get("Details"),
                    "impression": row.get("Impression"),
                    "entered_by": row.get("EnteredBy"),
                    "entered_on": parse_datetime(row.get("EnteredOn")) or timezone.now(),
                    "soft_deleted": bool(row.get("Soft_Deleted", False)),
                }
            )

        for row in load_json("tblMRIPelvisDetail"):
            img_id = row.get("ImagingID")
            if not ImagingInvestigation.objects.filter(imaging_id=img_id).exists():
                continue
            MRIPelvisDetail.objects.update_or_create(
                mri_detail_id=row["MRIDetailID"],
                defaults={
                    "imaging_id": img_id,
                    "tumour_dimension_1_cm": row.get("Tumour_Dimension_1_cm"),
                    "tumour_dimension_2_cm": row.get("Tumour_Dimension_2_cm"),
                    "tumour_dimension_3_cm": row.get("Tumour_Dimension_3_cm"),
                    "tumour_volume_cc": row.get("Tumour_Volume_cc"),
                    "cervix_involved": bool(row.get("Cervix_Involved", False)),
                    "cervical_stromal_invasion": bool(row.get("Cervical_Stromal_Invasion", False)),
                    "cervical_stromal_extent": row.get("Cervical_Stromal_Extent"),
                    "parametrium_involved": bool(row.get("Parametrium_Involved", False)),
                    "para_side": row.get("Para_Side"),
                    "para_left_involved": bool(row.get("Para_Left_Involved", False)),
                    "para_right_involved": bool(row.get("Para_Right_Involved", False)),
                    "para_left_extent_cm": row.get("Para_Left_Extent_cm"),
                    "para_right_extent_cm": row.get("Para_Right_Extent_cm"),
                    "uterine_corpus_involved": bool(row.get("Uterine_Corpus_Involved", False)),
                    "vaginal_involvement": bool(row.get("Vaginal_Involvement", False)),
                    "vaginal_extent": row.get("Vaginal_Extent"),
                    "bladder_status_id": row.get("BladderInvasionStatusID"),
                    "rectum_status_id": row.get("RectumInvasionStatusID"),
                    "hydronephrosis_left": bool(row.get("Hydronephrosis_Left", False)),
                    "hydronephrosis_right": bool(row.get("Hydronephrosis_Right", False)),
                    "nodes_present": bool(row.get("Nodes_Present", False)),
                    "pelvic_nodes_present": bool(row.get("Pelvic_Nodes_Present", False)),
                    "pa_nodes_present": bool(row.get("PA_Nodes_Present", False)),
                    "inguinal_nodes_present": bool(row.get("Inguinal_Nodes_Present", False)),
                    "distant_findings": row.get("Distant_Findings"),
                    "radiologist_impression": row.get("Radiologist_Impression"),
                }
            )

        # EBRT
        for row in load_json("tblEBRTCourse"):
            p_mr = row.get("MR_No")
            if not Patient.objects.filter(mr_no=p_mr).exists():
                continue
            EBRTCourse.objects.update_or_create(
                ebrt_course_id=row["EBRTCourseID"],
                defaults={
                    "patient_id": p_mr,
                    "course_sequence": row.get("Course_Sequence", 1) or 1,
                    "ebrt_intent_id": row.get("EBRTIntentID"),
                    "ebrt_technique_id": row.get("EBRTTechniqueID"),
                    "treatment_centre_id": row.get("TreatmentCentreID"),
                    "initial_rt_machine_id": row.get("InitialRTMachineID"),
                    "course_status_id": row.get("CourseStatusID"),
                    "total_dose_gy": row.get("Total_Dose_Gy"),
                    "total_fractions": row.get("Total_Fractions"),
                    "dose_per_fraction_gy": row.get("Dose_Per_Fraction_Gy"),
                    "ebrt_start_date": parse_date(row.get("EBRT_Start_Date")),
                    "ebrt_end_date": parse_date(row.get("EBRT_End_Date")),
                    "simulation_date": parse_date(row.get("Simulation_Date")),
                    "contouring_date": parse_date(row.get("Contouring_Date")),
                    "plan_approval_date": parse_date(row.get("Plan_Approval_Date")),
                    "treatment_interrupted": bool(row.get("Treatment_Interrupted", False)),
                    "interruption_days": row.get("Interruption_Days", 0) or 0,
                    "long_gap_notes": row.get("Long_Gap_Notes"),
                    "treatment_completed": bool(row.get("Treatment_Completed", False)),
                    "completion_notes": row.get("Completion_Notes"),
                    "entered_by": row.get("EnteredBy"),
                    "entered_on": parse_datetime(row.get("EnteredOn")) or timezone.now(),
                    "soft_deleted": bool(row.get("Soft_Deleted", False)),
                }
            )

        for row in load_json("tblEBRTCourseSite"):
            c_id = row.get("EBRTCourseID")
            s_id = row.get("EBRTSiteID")
            if EBRTCourse.objects.filter(ebrt_course_id=c_id).exists() and EBRTSite.objects.filter(site_id=s_id).exists():
                EBRTCourseSite.objects.update_or_create(
                    ebrt_course_site_id=row["EBRTCourseSiteID"],
                    defaults={"ebrt_course_id": c_id, "ebrt_site_id": s_id}
                )

        for row in load_json("tblEBRTInterruptionReasons"):
            c_id = row.get("EBRTCourseID")
            if not EBRTCourse.objects.filter(ebrt_course_id=c_id).exists():
                continue
            EBRTInterruption.objects.update_or_create(
                ebrt_interruption_id=row["EBRTInterruptionID"],
                defaults={
                    "ebrt_course_id": c_id,
                    "interruption_reason_id": row.get("InterruptionReasonID"),
                    "custom_text": row.get("Custom_Text"),
                    "days_lost": row.get("Days_Lost", 1) or 1,
                    "interruption_start_date": parse_date(row.get("Interruption_Start_Date")),
                    "interruption_end_date": parse_date(row.get("Interruption_End_Date")),
                    "notes": row.get("Notes"),
                }
            )

        # Brachytherapy
        for row in load_json("tblBrachyCourse"):
            p_mr = row.get("MR_No")
            if not Patient.objects.filter(mr_no=p_mr).exists():
                continue
            BrachyCourse.objects.update_or_create(
                brachy_course_id=row["BrachyCourseID"],
                defaults={
                    "patient_id": p_mr,
                    "course_sequence": row.get("Course_Sequence", 1) or 1,
                    "brachy_received": bool(row.get("Brachy_Received", True)),
                    "brachy_source_id": row.get("BrachySourceID"),
                    "brachy_dosing_id": row.get("BrachyDosingID"),
                    "treatment_centre_id": row.get("TreatmentCentreID"),
                    "course_status_id": row.get("CourseStatusID"),
                    "linked_ebrt_course_id": row.get("Linked_EBRTCourseID") if EBRTCourse.objects.filter(ebrt_course_id=row.get("Linked_EBRTCourseID")).exists() else None,
                    "prescription_dose_gy": row.get("Prescription_Dose_Gy"),
                    "total_fractions_planned": row.get("Total_Fractions_Planned", 3) or 3,
                    "total_fractions_delivered": row.get("Total_Fractions_Delivered", 0) or 0,
                    "brachy_start_date": parse_date(row.get("Brachy_Start_Date")),
                    "brachy_end_date": parse_date(row.get("Brachy_End_Date")),
                    "alpha_beta_tumor": row.get("AlphaBeta_Tumor", 10.0) or 10.0,
                    "alpha_beta_bladder": row.get("AlphaBeta_Bladder", 3.0) or 3.0,
                    "alpha_beta_rectum": row.get("AlphaBeta_Rectum", 3.0) or 3.0,
                    "alpha_beta_sigmoid": row.get("AlphaBeta_Sigmoid", 3.0) or 3.0,
                    "completion_status": row.get("Completion_Status"),
                    "completion_notes": row.get("Completion_Notes"),
                    "entered_by": row.get("EnteredBy"),
                    "entered_on": parse_datetime(row.get("EnteredOn")) or timezone.now(),
                    "soft_deleted": bool(row.get("Soft_Deleted", False)),
                }
            )

        for row in load_json("tblBrachySessions"):
            bc_id = row.get("BrachyCourseID")
            if not BrachyCourse.objects.filter(brachy_course_id=bc_id).exists():
                continue
            BrachySession.objects.update_or_create(
                brachy_session_id=row["BrachySessionID"],
                defaults={
                    "brachy_course_id": bc_id,
                    "session_number": row.get("Session_Number", 1) or 1,
                    "session_date": parse_date(row.get("Session_Date")) or date.today(),
                    "applicator_id": row["BrachyApplicatorID"],
                    "image_guidance_id": row["BrachyImageGuidanceID"],
                    "anaesthesia_type_id": row.get("AnaesthesiaTypeID"),
                    "is_template_id": row.get("ISTemplateID"),
                    "session_status_id": row.get("BrachySessionStatusID"),
                    "procedure_performed_by": row.get("Procedure_Performed_By", "Clinician"),
                    "procedure_notes": row.get("Procedure_Notes", ""),
                    "insertion_complications": row.get("Insertion_Complications", "None"),
                    "tandem_length_cm": row.get("Tandem_Length_cm"),
                    "ovoid_size_mm": row.get("Ovoid_Size_mm"),
                    "ring_diameter_mm": row.get("Ring_Diameter_mm"),
                    "number_of_needles": row.get("Number_Of_Needles", 0) or 0,
                    "packing_adequate": bool(row.get("Packing_Adequate", True)),
                    "imaging_done": bool(row.get("Imaging_Done", True)),
                    "fractions_planned": row.get("Fractions_Planned", 1) or 1,
                }
            )

        for row in load_json("tblBrachyFractions"):
            bs_id = row.get("BrachySessionID")
            if not BrachySession.objects.filter(brachy_session_id=bs_id).exists():
                continue
            BrachyFraction.objects.update_or_create(
                brachy_fraction_id=row["BrachyFractionID"],
                defaults={
                    "brachy_session_id": bs_id,
                    "fraction_number_in_session": row.get("Fraction_Number_In_Session", 1) or 1,
                    "overall_fraction_number": row.get("Overall_Fraction_Number", 1) or 1,
                    "fraction_date": parse_date(row.get("Fraction_Date")) or date.today(),
                    "prescribed_dose_gy": row.get("Prescribed_Dose_Gy"),
                    "dose_delivered_gy": row.get("Dose_Delivered_Gy"),
                    "total_dwell_time_seconds": row.get("Total_Dwell_Time_seconds", 0) or 0,
                    "bladder_dose_2cc_gy": row.get("Bladder_Dose_2cc_Gy"),
                    "rectum_dose_2cc_gy": row.get("Rectum_Dose_2cc_Gy"),
                    "sigmoid_dose_2cc_gy": row.get("Sigmoid_Dose_2cc_Gy"),
                    "bowel_dose_2cc_gy": row.get("Bowel_Dose_2cc_Gy"),
                    "bladder_point_dose_gy": row.get("Bladder_Point_Dose_Gy"),
                    "rectum_point_dose_gy": row.get("Rectum_Point_Dose_Gy"),
                    "hrctv_d90_gy": row.get("HRCTV_D90_Gy"),
                    "hrctv_d98_gy": row.get("HRCTV_D98_Gy"),
                    "irctv_d90_gy": row.get("IRCTV_D90_Gy"),
                    "irctv_d98_gy": row.get("IRCTV_D98_Gy"),
                    "gtv_d98_gy": row.get("GTV_D98_Gy"),
                    "volume_hrctv_cc": row.get("Volume_HRCTV_cc"),
                    "volume_irctv_cc": row.get("Volume_IRCTV_cc"),
                    "volume_gtv_cc": row.get("Volume_GTV_cc"),
                    "fraction_status_id": row.get("BrachyFractionStatusID"),
                    "fraction_notes": row.get("Fraction_Notes", ""),
                }
            )

        # Concurrent Chemotherapy
        for row in load_json("tblConcurrentChemoCourse"):
            p_mr = row.get("MR_No")
            if not Patient.objects.filter(mr_no=p_mr).exists():
                continue
            ConcurrentChemoCourse.objects.update_or_create(
                conc_chemo_course_id=row["ConcChemoCourseID"],
                defaults={
                    "patient_id": p_mr,
                    "concurrent_received": bool(row.get("Concurrent_Received", True)),
                    "chemo_regimen_id": row.get("ChemoRegimenID"),
                    "cycle_frequency_days": row.get("Cycle_Frequency_Days", 7) or 7,
                    "planned_cycles": row.get("Planned_Cycles", 5) or 5,
                    "received_cycles": row.get("Received_Cycles", 0) or 0,
                    "conc_chemo_start_date": parse_date(row.get("ConcChemo_Start_Date")),
                    "conc_chemo_end_date": parse_date(row.get("ConcChemo_End_Date")),
                    "linked_ebrt_course_id": row.get("Linked_EBRTCourseID") if EBRTCourse.objects.filter(ebrt_course_id=row.get("Linked_EBRTCourseID")).exists() else None,
                    "completion_status": row.get("Completion_Status"),
                    "discontinuation_reason": row.get("Discontinuation_Reason"),
                    "notes": row.get("Notes"),
                    "entered_by": row.get("EnteredBy"),
                    "entered_on": parse_datetime(row.get("EnteredOn")) or timezone.now(),
                    "soft_deleted": bool(row.get("Soft_Deleted", False)),
                }
            )

        for row in load_json("tblConcurrentChemoCycles"):
            cc_id = row.get("ConcChemoCourseID")
            if not ConcurrentChemoCourse.objects.filter(conc_chemo_course_id=cc_id).exists():
                continue
            ConcurrentChemoCycle.objects.update_or_create(
                conc_chemo_cycle_id=row["ConcChemoCycleID"],
                defaults={
                    "course_id": cc_id,
                    "cycle_number": row.get("Cycle_Number", 1) or 1,
                    "cycle_date": parse_date(row.get("Cycle_Date")) or date.today(),
                    "cycle_status": row.get("Cycle_Status", "Administered"),
                    "pre_cycle_notes": row.get("Pre_Cycle_Notes"),
                    "cycle_toxicity": row.get("Cycle_Toxicity"),
                    "post_cycle_notes": row.get("Post_Cycle_Notes"),
                }
            )

        for row in load_json("tblConcurrentChemoDrugs"):
            cyc_id = row.get("ConcChemoCycleID")
            if not ConcurrentChemoCycle.objects.filter(conc_chemo_cycle_id=cyc_id).exists():
                continue
            ConcurrentChemoDrug.objects.update_or_create(
                conc_chemo_drug_id=row["ConcChemoDrugID"],
                defaults={
                    "cycle_id": cyc_id,
                    "chemo_agent_id": row["ChemoAgentID"],
                    "dose": row.get("Dose"),
                    "dose_unit_id": row.get("DoseUnitID"),
                    "dose_mg": row.get("Dose_mg"),
                    "dose_per_m2": row.get("Dose_per_m2"),
                    "bsa_m2": row.get("BSA_m2"),
                    "chemo_route_id": row.get("ChemoRouteID"),
                    "administered": bool(row.get("Administered", True)),
                    "reason_if_not_administered": row.get("Reason_If_Not_Administered"),
                }
            )

        # NACT
        for row in load_json("tblNACTCourse"):
            p_mr = row.get("MR_No")
            if not Patient.objects.filter(mr_no=p_mr).exists():
                continue
            NACTCourse.objects.update_or_create(
                nact_course_id=row["NACTCourseID"],
                defaults={
                    "patient_id": p_mr,
                    "course_sequence": row.get("Course_Sequence", 1) or 1,
                    "nact_received": bool(row.get("NACT_Received", True)),
                    "chemo_regimen_id": row.get("ChemoRegimenID"),
                    "cycle_frequency_days": row.get("Cycle_Frequency_Days", 21) or 21,
                    "planned_cycles": row.get("Planned_Cycles", 3) or 3,
                    "received_cycles": row.get("Received_Cycles", 0) or 0,
                    "nact_start_date": parse_date(row.get("NACT_Start_Date")),
                    "nact_end_date": parse_date(row.get("NACT_End_Date")),
                    "response_to_nact_id": row.get("ResponseID"),
                    "nact_status_id": row.get("NACTStatusID"),
                    "post_nact_assessment_done": bool(row.get("PostNACT_Assessment_Done", False)),
                    "post_nact_mri_done": bool(row.get("PostNACT_MRI_Done", False)),
                    "notes": row.get("Notes"),
                    "entered_by": row.get("EnteredBy"),
                    "entered_on": parse_datetime(row.get("EnteredOn")) or timezone.now(),
                    "soft_deleted": bool(row.get("Soft_Deleted", False)),
                }
            )

        for row in load_json("tblNACTCycles"):
            nc_id = row.get("NACTCourseID")
            if not NACTCourse.objects.filter(nact_course_id=nc_id).exists():
                continue
            NACTCycle.objects.update_or_create(
                nact_cycle_id=row["NACTCycleID"],
                defaults={
                    "course_id": nc_id,
                    "cycle_number": row.get("Cycle_Number", 1) or 1,
                    "cycle_date": parse_date(row.get("Cycle_Date")) or date.today(),
                    "cycle_status": row.get("Cycle_Status", "Administered"),
                    "cycle_toxicity": row.get("Cycle_Toxicity"),
                    "pre_cycle_notes": row.get("Pre_Cycle_Notes"),
                }
            )

        for row in load_json("tblNACTDrugs"):
            cyc_id = row.get("NACTCycleID")
            if not NACTCycle.objects.filter(nact_cycle_id=cyc_id).exists():
                continue
            NACTDrug.objects.update_or_create(
                nact_drug_id=row["NACTDrugID"],
                defaults={
                    "cycle_id": cyc_id,
                    "chemo_agent_id": row["ChemoAgentID"],
                    "dose": row.get("Dose"),
                    "dose_unit_id": row.get("DoseUnitID"),
                    "chemo_route_id": row.get("ChemoRouteID"),
                    "administered": bool(row.get("Administered", True)),
                }
            )

        # Adjuvant Chemo
        for row in load_json("tblAdjuvantCourse"):
            p_mr = row.get("MR_No")
            if not Patient.objects.filter(mr_no=p_mr).exists():
                continue
            AdjuvantChemoCourse.objects.update_or_create(
                adjuvant_course_id=row["AdjuvantCourseID"],
                defaults={
                    "patient_id": p_mr,
                    "course_sequence": row.get("Course_Sequence", 1) or 1,
                    "adjuvant_received": bool(row.get("Adjuvant_Received", True)),
                    "planned_cycles": row.get("Planned_Cycles", 4) or 4,
                    "received_cycles": row.get("Received_Cycles", 0) or 0,
                    "chemo_status_id": row.get("ChemoStatusID"),
                    "notes": row.get("Notes"),
                }
            )

        # Follow-Up
        for row in load_json("tblFollowUpStatus"):
            p_mr = row.get("MR_No")
            if not Patient.objects.filter(mr_no=p_mr).exists():
                continue
            FollowUpStatus.objects.update_or_create(
                follow_up_status_id=row["FollowUpStatusID"],
                defaults={
                    "patient_id": p_mr,
                    "follow_up_date": parse_date(row.get("FollowUp_Date")) or date.today(),
                    "contact_type_id": row.get("FollowUpContactTypeID"),
                    "proxy_status_id": row.get("ProxyStatusID"),
                    "disease_status_id": row.get("DiseaseStatusID"),
                    "response_status_id": row.get("ResponseID"),
                    "recurrence_detected": bool(row.get("Recurrence_Detected", False)),
                    "date_of_recurrence": parse_date(row.get("Date_Of_Recurrence")),
                    "recurrence_confirmed_by": row.get("Recurrence_Confirmed_By"),
                    "recurrence_local": bool(row.get("Recurrence_Local", False)),
                    "recurrence_nodal": bool(row.get("Recurrence_Nodal", False)),
                    "recurrence_distant": bool(row.get("Recurrence_Distant", False)),
                    "second_primary": bool(row.get("Second_Primary", False)),
                    "node_pelvic": bool(row.get("Node_Pelvic", False)),
                    "node_para_aortic": bool(row.get("Node_ParaAortic", False)),
                    "node_inguinal": bool(row.get("Node_Inguinal", False)),
                    "distant_nodal_other": bool(row.get("Distant_Nodal_Other", False)),
                    "distant_visceral": bool(row.get("Distant_Visceral", False)),
                    "recurrence_site_id": row.get("RecurrenceSiteID"),
                    "recurrence_treatment_plan": row.get("Recurrence_Treatment_Plan"),
                    "death_reported": bool(row.get("Death_Reported", False)),
                    "date_of_death": parse_date(row.get("Date_Of_Death")),
                    "cause_of_death_id": row.get("CauseOfDeathID"),
                    "performance_notes": row.get("Performance_Notes"),
                    "next_fu_date": parse_date(row.get("Next_FU_Date")),
                    "next_fu_notes": row.get("Next_FU_Notes"),
                    "entered_by": row.get("EnteredBy"),
                    "entered_on": parse_datetime(row.get("EnteredOn")) or timezone.now(),
                    "soft_deleted": bool(row.get("Soft_Deleted", False)),
                }
            )

        # Audit Log
        for row in load_json("tblAuditLog"):
            AuditLog.objects.create(
                log_id=row["LogID"],
                log_datetime=parse_datetime(row.get("LogDateTime")) or timezone.now(),
                username=row.get("Username", "system"),
                full_name=row.get("FullName"),
                action=row.get("Action", "ACTION"),
                table_affected=row.get("TableAffected", ""),
                record_ref=row.get("RecordRef", ""),
                notes=row.get("Notes"),
                field_name=row.get("FieldName"),
                old_value=str(row.get("OldValue", "")),
                new_value=str(row.get("NewValue", "")),
                reason=row.get("Reason"),
            )

        self.stdout.write(self.style.SUCCESS("MS Access data migration completed successfully!"))
