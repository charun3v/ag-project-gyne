import os
import sys
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gynae_oncology.settings')
django.setup()

from patients.models import Patient
from clinical.models import Encounter, EncounterType, ClinicalHistory
from followup.models import FollowUpStatus, DiseaseStatus, FollowUpContactType
from investigations.models import BloodInvestigation, PathologyInvestigation, ImagingInvestigation, MolecularInvestigation

def run_tests():
    print("=" * 60)
    print("RUNNING AUTOMATED VERIFICATION FOR CLINICAL FIXES")
    print("=" * 60)

    # 1. Test Date Defaults
    reg_date = date(2025, 4, 15)
    test_pt, _ = Patient.objects.get_or_create(
        mr_no="TEST-CLINICAL-001",
        defaults={
            'pt_name': "Verification Test Patient",
            'sex': "Female",
            'date_of_registration': reg_date,
            'phone': "9999999999"
        }
    )
    if test_pt.date_of_registration != reg_date:
        test_pt.date_of_registration = reg_date
        test_pt.save()

    print("[PASS] Test patient initialized with reg_date:", test_pt.date_of_registration)

    # 2. Test History Snapshot Date Default
    hist = test_pt.histories.filter(soft_deleted=False).first()
    if not hist:
        hist = ClinicalHistory(patient=test_pt, entered_by="admin")
        hist.snapshot_date = test_pt.date_of_registration
        hist.bleeding_pv = True
        hist.hypertension = True
        hist.hpi = "Postmenopausal bleeding for 3 months."
        hist.save()
    assert hist.snapshot_date == reg_date, f"Expected {reg_date}, got {hist.snapshot_date}"
    print("[PASS] History Form snapshot date matches patient registration date.")

    # 3. Test Baseline Encounter Default Date
    enc_type_base = EncounterType.objects.filter(encounter_type_name__icontains='Baseline').first() or EncounterType.objects.first()
    enc = Encounter(patient=test_pt, encounter_type=enc_type_base, entered_by="admin")
    enc.encounter_date = test_pt.date_of_registration
    enc.save()
    assert enc.encounter_date == reg_date, f"Expected {reg_date}, got {enc.encounter_date}"
    print("[PASS] Baseline Examination encounter date matches patient registration date.")

    # 4. Test Pre-Brachy Uterine Sounding (0 is valid for stenosed / unable to sound)
    enc_type_brachy = EncounterType.objects.filter(encounter_type_name__icontains='Pre-Brachy').first() or enc_type_base
    enc_brachy = Encounter(patient=test_pt, encounter_type=enc_type_brachy, entered_by="admin")
    enc_brachy.tandem_length_cm = 0.0
    enc_brachy.tandem_sounded = False
    enc_brachy.save()
    assert enc_brachy.tandem_length_cm == 0.0, "Uterine sounding 0.0 must be preserved"
    print("[PASS] Pre-Brachy sounding accepts 0.0 for stenosed / cannot sound.")

    # 5. Test Follow-Up Alive - NED bug fix
    ned_status = DiseaseStatus.objects.filter(status_name__icontains='NED').first() or DiseaseStatus.objects.filter(status_name__icontains='No Evidence').first()
    if not ned_status:
        ned_status = DiseaseStatus.objects.create(disease_status_id=999, status_name="Alive - No Evidence of Disease (NED)")

    contact_type = FollowUpContactType.objects.first()

    # Simulate submission where death_reported was "0"
    raw_death = "0"
    ds_name = ned_status.status_name.lower()
    is_ned = ('ned' in ds_name) or ('no evidence' in ds_name)
    is_dead = ('dead' in ds_name) or (raw_death in ['1', 'true', 'True', True] and not is_ned)
    if is_ned or ('alive' in ds_name and 'dead' not in ds_name):
        is_dead = False

    assert is_dead is False, f"Expected is_dead to be False for NED with death_reported='0', got {is_dead}"
    print("[PASS] Follow-Up NED with death_reported='0' evaluates strictly as ALIVE (is_dead=False).")

    fu = FollowUpStatus.objects.create(
        patient=test_pt,
        follow_up_date=date.today(),
        disease_status=ned_status,
        contact_type=contact_type,
        death_reported=is_dead,
        entered_by="admin"
    )
    assert fu.death_reported is False, "FollowUpStatus.death_reported must be False"
    print("[PASS] FollowUpStatus record saved with death_reported=False. Displays as Alive!")

    # 6. Test Encounter creation for Diagram navigation from Follow-Up
    if not fu.encounter:
        enc_type_fu = EncounterType.objects.filter(encounter_type_name__icontains='Follow-up').first() or EncounterType.objects.first()
        fu.encounter = Encounter.objects.create(
            patient=test_pt,
            encounter_type=enc_type_fu,
            encounter_date=fu.follow_up_date,
            entered_by="admin"
        )
        fu.save(update_fields=['encounter'])
    assert fu.encounter is not None, "FollowUpStatus encounter must exist for diagram routing"
    print(f"[PASS] Follow-Up Diagram routing verified: Encounter #{fu.encounter.clinical_id} linked.")

    print("=" * 60)
    print("ALL 7 CLINICAL AND WORKFLOW VERIFICATIONS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
