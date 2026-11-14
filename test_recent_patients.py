"""
Unit and Integration Tests for User-Specific Recent Patients Worklist.
Verifies:
1. User-specific patient access tracking.
2. Order preservation (most recently accessed patient appears first).
3. Maximum 15 patients limit per user.
4. User isolation (User A's recent list does not bleed into User B's list).
5. Automatic capture via RecentPatientMiddleware when any view with mr_no is accessed.
6. Dashboard view presentation of recent 15 patients.
"""

import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gynae_oncology.settings')
import django
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from patients.models import Patient
from core.recent_patients import (
    ensure_recent_patient_table,
    record_patient_opened,
    get_user_recent_mr_nos,
    RecentPatientMiddleware
)
from core.views import dashboard_view

def run_tests():
    print("====================================================")
    print("Starting User-Specific Recent Patients Worklist Tests")
    print("====================================================")

    # 1. Setup Test Users
    user1, _ = User.objects.get_or_create(username='dr_sharma_test', defaults={'first_name': 'Dr. Sharma'})
    user2, _ = User.objects.get_or_create(username='dr_nithin_test', defaults={'first_name': 'Dr. Nithin'})

    # 2. Setup Test Patients (20 patients to test the 15 limit)
    test_patients = []
    for i in range(1, 21):
        mr = f"TEST-RECENT-{i:03d}"
        pt, _ = Patient.objects.get_or_create(
            mr_no=mr,
            defaults={
                'pt_name': f"Recent Test Patient {i}",
                'sex': 'Female',
                'phone': f"98765432{i:02d}"
            }
        )
        test_patients.append(pt)

    print(f"  ✓ Prepared {len(test_patients)} test patients.")

    # 3. Test Recording & Ordering for User 1
    print("\n[Test 1] Testing recording and ordering of opened patients...")
    ensure_recent_patient_table()

    # User 1 opens Patient 1, then Patient 2, then Patient 3
    record_patient_opened(user1, test_patients[0].mr_no)
    record_patient_opened(user1, test_patients[1].mr_no)
    record_patient_opened(user1, test_patients[2].mr_no)

    recent_user1 = get_user_recent_mr_nos(user1, limit=15)
    print(f"  - User 1 top 3 recent MRs: {recent_user1[:3]}")
    assert recent_user1[0] == test_patients[2].mr_no, f"Most recently opened patient must be #1 (expected {test_patients[2].mr_no}, got {recent_user1[0]})"
    assert recent_user1[1] == test_patients[1].mr_no, f"Second recently opened must be #2"
    assert recent_user1[2] == test_patients[0].mr_no, f"First opened must be #3"
    print("  ✓ Chronological LIFO order verified.")

    # 4. Test User Isolation (User 2 opens different patients)
    print("\n[Test 2] Testing user isolation...")
    record_patient_opened(user2, test_patients[18].mr_no)
    record_patient_opened(user2, test_patients[19].mr_no)

    recent_user2 = get_user_recent_mr_nos(user2, limit=15)
    print(f"  - User 2 top 2 recent MRs: {recent_user2[:2]}")
    assert recent_user2[0] == test_patients[19].mr_no
    assert recent_user2[1] == test_patients[18].mr_no
    assert test_patients[0].mr_no != recent_user2[0]
    print("  ✓ User isolation verified (User 2's list is completely independent of User 1).")

    # 5. Test Maximum 15 Patients Limit
    print("\n[Test 3] Testing 15-patient cap...")
    # User 1 opens all 20 patients in sequence
    for pt in test_patients:
        record_patient_opened(user1, pt.mr_no)

    capped_list = get_user_recent_mr_nos(user1, limit=15)
    print(f"  - Total returned for User 1: {len(capped_list)} (limit requested: 15)")
    assert len(capped_list) == 15, f"Expected exactly 15 patients, got {len(capped_list)}"
    # The last opened patient should be Patient 20 (index 19)
    assert capped_list[0] == test_patients[19].mr_no
    # The 15th patient should be Patient 6 (index 5)
    assert capped_list[14] == test_patients[5].mr_no
    # Patient 1 (index 0) should have dropped off the 15-patient list
    assert test_patients[0].mr_no not in capped_list, "Patient 1 should have fallen off the top 15 list"
    print("  ✓ Exactly 15 most recent patients returned and older patients dropped off.")

    # 6. Test Dashboard View Output
    print("\n[Test 4] Testing Dashboard view integration...")
    rf = RequestFactory()
    req = rf.get('/dashboard/')
    req.user = user1
    res = dashboard_view(req)
    assert res.status_code == 200
    assert 'patients' in res.context_data
    dash_patients = res.context_data['patients']
    print(f"  - Dashboard returned patients count: {len(dash_patients)}")
    assert len(dash_patients) == 15, f"Dashboard must show at most 15 patients, got {len(dash_patients)}"
    assert dash_patients[0]['mr_no'] == test_patients[19].mr_no
    print("  ✓ Dashboard renders exactly the user's top 15 recent patients in order.")

    # 7. Test Middleware Interception
    print("\n[Test 5] Testing RecentPatientMiddleware automatic recording...")
    middleware = RecentPatientMiddleware(lambda r: None)
    dummy_req = rf.get(f"/clinical/{test_patients[0].mr_no}/examination/")
    dummy_req.user = user1

    # Simulate opening Patient 1 via URL kwargs
    middleware.process_view(dummy_req, lambda r: None, (), {'mr_no': test_patients[0].mr_no})

    # Patient 1 should now jump back to #1 spot on User 1's list!
    updated_recent = get_user_recent_mr_nos(user1, limit=15)
    assert updated_recent[0] == test_patients[0].mr_no, "Patient 1 should jump to #1 spot after middleware capture"
    print("  ✓ RecentPatientMiddleware successfully recorded patient access and bumped to #1 spot.")

    print("\n====================================================")
    print("ALL RECENT PATIENTS WORKLIST TESTS PASSED! ✓")
    print("====================================================")

if __name__ == '__main__':
    run_tests()
