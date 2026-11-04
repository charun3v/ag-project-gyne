from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from datetime import date
from django.utils import timezone

from patients.models import Patient
from radiotherapy.models import (
    BrachyCourse,
    BrachySession,
    ApplicatorType,
    ApplicatorMeasurementDefinition,
    ApplicatorFieldRule,
    BrachyImageGuidance,
    BrachySessionStatus,
)
from radiotherapy.validators import validate_applicator_measurements
from radiotherapy.forms import BrachySessionForm

User = get_user_model()


class ApplicatorFieldValidationTests(TestCase):
    def setUp(self):
        # Users
        self.admin_user = User.objects.create_superuser(
            username='admin_doc',
            password='Password@123',
            email='admin@kmio.org'
        )
        self.clinical_user = User.objects.create_user(
            username='resident_doc',
            password='Password@123',
            email='resident@kmio.org',
            is_staff=False,
            is_superuser=False
        )

        # Patient & Course
        self.patient = Patient.objects.create(
            mr_no='MR-TEST-APP',
            pt_name='Applicator Test Patient',
            date_of_birth=date(1974, 1, 1),
            sex='Female'
        )
        self.course = BrachyCourse.objects.create(
            patient=self.patient,
            course_sequence=1,
            total_fractions_planned=3
        )

        self.guidance = BrachyImageGuidance.objects.first()
        if not self.guidance:
            self.guidance = BrachyImageGuidance.objects.create(guidance_id=1, guidance_name='CT')

        self.status_planned = BrachySessionStatus.objects.filter(status_id=1).first()
        if not self.status_planned:
            self.status_planned = BrachySessionStatus.objects.create(status_id=1, status_name='Planned')

        self.status_completed = BrachySessionStatus.objects.filter(status_id=2).first()
        if not self.status_completed:
            self.status_completed = BrachySessionStatus.objects.create(status_id=2, status_name='Completed')

        # Applicator types
        self.app_tandem_only = ApplicatorType.objects.get(name='Tandem only')
        self.app_tandem_ovoids = ApplicatorType.objects.get(name='Tandem and Ovoids')
        self.app_ovoids_only = ApplicatorType.objects.get(name='Ovoids only')
        self.app_tandem_ring = ApplicatorType.objects.get(name='Tandem and Ring')
        self.app_tandem_ring_needles = ApplicatorType.objects.get(name='Tandem, Ring and Needles')
        self.app_interstitial = ApplicatorType.objects.get(name='Interstitial needles only')

    def test_01_tandem_only_requires_only_tandem_length(self):
        """1. Tandem only requires only Tandem length."""
        # Missing tandem length -> error
        errs = validate_applicator_measurements(self.app_tandem_only, {'tandem_length_cm': None})
        self.assertIn('tandem_length_cm', errs)
        self.assertIn('is required for Tandem only', errs['tandem_length_cm'])

        # Valid tandem length -> clean
        errs_valid = validate_applicator_measurements(self.app_tandem_only, {'tandem_length_cm': 6.0})
        self.assertEqual(errs_valid, {})

        # Unexpected measurement provided -> error
        errs_invalid = validate_applicator_measurements(self.app_tandem_only, {
            'tandem_length_cm': 6.0,
            'ring_diameter_mm': 30.0
        })
        self.assertIn('ring_diameter_mm', errs_invalid)
        self.assertIn('does not apply to the selected applicator', errs_invalid['ring_diameter_mm'])

    def test_02_tandem_and_ovoids_requires_tandem_ovoid_dia_and_ovoid_length(self):
        """2. Tandem and Ovoids requires Tandem length, Ovoid diameter and Ovoid length."""
        # All missing
        errs = validate_applicator_measurements(self.app_tandem_ovoids, {})
        self.assertIn('tandem_length_cm', errs)
        self.assertIn('ovoid_diameter_mm', errs)
        self.assertIn('ovoid_length_mm', errs)

        # Only tandem provided
        errs_partial = validate_applicator_measurements(self.app_tandem_ovoids, {'tandem_length_cm': 6.0})
        self.assertNotIn('tandem_length_cm', errs_partial)
        self.assertIn('ovoid_diameter_mm', errs_partial)
        self.assertIn('ovoid_length_mm', errs_partial)

        # All three provided -> valid
        errs_valid = validate_applicator_measurements(self.app_tandem_ovoids, {
            'tandem_length_cm': 6.0,
            'ovoid_diameter_mm': 20.0,
            'ovoid_length_mm': 30.0
        })
        self.assertEqual(errs_valid, {})

    def test_03_ovoids_only_requires_both_ovoid_measurements(self):
        """3. Ovoids only requires both Ovoid measurements."""
        # Missing both
        errs = validate_applicator_measurements(self.app_ovoids_only, {})
        self.assertIn('ovoid_diameter_mm', errs)
        self.assertIn('ovoid_length_mm', errs)
        self.assertNotIn('tandem_length_cm', errs)

        # Both valid
        errs_valid = validate_applicator_measurements(self.app_ovoids_only, {
            'ovoid_diameter_mm': 20.0,
            'ovoid_length_mm': 25.0
        })
        self.assertEqual(errs_valid, {})

        # Inapplicable tandem length supplied
        errs_invalid = validate_applicator_measurements(self.app_ovoids_only, {
            'ovoid_diameter_mm': 20.0,
            'ovoid_length_mm': 25.0,
            'tandem_length_cm': 5.0
        })
        self.assertIn('tandem_length_cm', errs_invalid)

    def test_04_tandem_and_ring_requires_tandem_and_ring(self):
        """4. Tandem and Ring requires Tandem length and Ring diameter."""
        errs = validate_applicator_measurements(self.app_tandem_ring, {})
        self.assertIn('tandem_length_cm', errs)
        self.assertIn('ring_diameter_mm', errs)
        self.assertNotIn('ovoid_diameter_mm', errs)

        errs_valid = validate_applicator_measurements(self.app_tandem_ring, {
            'tandem_length_cm': 6.0,
            'ring_diameter_mm': 30.0
        })
        self.assertEqual(errs_valid, {})

    def test_05_tandem_ring_and_needles_requires_all_three(self):
        """5. Tandem, Ring and Needles requires all three applicable measurements."""
        errs = validate_applicator_measurements(self.app_tandem_ring_needles, {})
        self.assertIn('tandem_length_cm', errs)
        self.assertIn('ring_diameter_mm', errs)
        self.assertIn('needle_count', errs)

        errs_valid = validate_applicator_measurements(self.app_tandem_ring_needles, {
            'tandem_length_cm': 6.0,
            'ring_diameter_mm': 30.0,
            'needle_count': 12
        })
        self.assertEqual(errs_valid, {})

    def test_06_interstitial_needles_only_requires_number_of_needles(self):
        """6. Interstitial needles only requires Number of needles."""
        errs = validate_applicator_measurements(self.app_interstitial, {})
        self.assertIn('needle_count', errs)
        self.assertNotIn('tandem_length_cm', errs)

        errs_valid = validate_applicator_measurements(self.app_interstitial, {'needle_count': 14})
        self.assertEqual(errs_valid, {})

    def test_07_non_applicable_fields_rejected_or_ignored_safely(self):
        """7. Non-applicable fields are rejected by validator and safely cleared on form save."""
        # Server validation rejects non-applicable fields with values
        errs = validate_applicator_measurements(self.app_tandem_only, {
            'tandem_length_cm': 6.0,
            'ovoid_diameter_mm': 20.0
        })
        self.assertIn('ovoid_diameter_mm', errs)

        # In Form clean(), non-applicable fields are set to None so not saved accidentally
        form = BrachySessionForm(data={
            'session_number': 1,
            'session_date': date.today(),
            'applicator': self.app_tandem_only.id,
            'image_guidance': self.guidance.guidance_id,
            'tandem_length_cm': 6.0,
        })
        self.assertTrue(form.is_valid())
        self.assertIsNone(form.cleaned_data['ring_diameter_mm'])
        self.assertIsNone(form.cleaned_data['ovoid_diameter_mm'])

    def test_08_needle_count_rejects_zero_negative_and_decimal(self):
        """8. Needle count rejects zero, negative and decimal values."""
        # Zero
        errs_zero = validate_applicator_measurements(self.app_interstitial, {'needle_count': 0})
        self.assertIn('needle_count', errs_zero)

        # Negative
        errs_neg = validate_applicator_measurements(self.app_interstitial, {'needle_count': -4})
        self.assertIn('needle_count', errs_neg)

        # Decimal
        errs_dec = validate_applicator_measurements(self.app_interstitial, {'needle_count': 4.5})
        self.assertIn('needle_count', errs_dec)

        # Valid positive integer
        errs_pos = validate_applicator_measurements(self.app_interstitial, {'needle_count': 8})
        self.assertEqual(errs_pos, {})

    def test_09_decimal_measurements_reject_zero_and_negative(self):
        """9. Required decimal measurements reject zero and negative values."""
        errs_zero = validate_applicator_measurements(self.app_tandem_only, {'tandem_length_cm': 0.0})
        self.assertIn('tandem_length_cm', errs_zero)
        self.assertIn('must be a positive decimal value', errs_zero['tandem_length_cm'])

        errs_neg = validate_applicator_measurements(self.app_tandem_only, {'tandem_length_cm': -3.5})
        self.assertIn('tandem_length_cm', errs_neg)

    def test_10_editing_saved_record_restores_applicable_values(self):
        """10. Editing a saved record restores its applicable values."""
        session = BrachySession.objects.create(
            brachy_course=self.course,
            session_number=1,
            session_date=date.today(),
            applicator=self.app_tandem_ovoids,
            image_guidance=self.guidance,
            tandem_length_cm=6.0,
            ovoid_diameter_mm=22.0,
            ovoid_length_mm=30.0
        )
        c = Client()
        c.force_login(self.clinical_user)
        resp = c.get(reverse('brachy_session_edit', kwargs={
            'mr_no': self.patient.mr_no,
            'course_id': self.course.brachy_course_id,
            'session_id': session.brachy_session_id
        }))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('6.0', content)
        self.assertIn('22.0', content)
        self.assertIn('30.0', content)

    def test_11_changing_applicator_updates_visible_fields(self):
        """11. Changing the applicator API endpoint returns correct active rules."""
        c = Client()
        c.force_login(self.clinical_user)
        # Tandem only API check
        resp1 = c.get(reverse('api_applicator_rules', kwargs={'applicator_id': self.app_tandem_only.id}))
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()
        enabled_codes1 = [r['code'] for r in data1['rules'] if r['enabled']]
        self.assertEqual(enabled_codes1, ['tandem_length_cm'])

        # Tandem and Ring API check
        resp2 = c.get(reverse('api_applicator_rules', kwargs={'applicator_id': self.app_tandem_ring.id}))
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        enabled_codes2 = [r['code'] for r in data2['rules'] if r['enabled']]
        self.assertIn('tandem_length_cm', enabled_codes2)
        self.assertIn('ring_diameter_mm', enabled_codes2)

    def test_12_admin_changes_mapping_immediately_affects_unapproved_records(self):
        """12. Admin changes to the mapping immediately affect new unapproved records."""
        # Find the rule for Tandem only -> needle_count
        needle_def = ApplicatorMeasurementDefinition.objects.get(code='needle_count')
        rule = ApplicatorFieldRule.objects.get(
            applicator_type=self.app_tandem_only,
            measurement_definition=needle_def
        )
        # Admin enables and requires needle_count on Tandem only
        rule.enabled = True
        rule.required = True
        rule.save()

        # Immediate validation without code modification now requires needle_count
        errs = validate_applicator_measurements(self.app_tandem_only, {'tandem_length_cm': 6.0})
        self.assertIn('needle_count', errs)

        # Reset back for clean state
        rule.enabled = False
        rule.required = False
        rule.save()

    def test_13_historical_approved_applications_remain_unchanged(self):
        """13. Historical approved applications remain unchanged after configuration changes."""
        session = BrachySession.objects.create(
            brachy_course=self.course,
            session_number=1,
            session_date=date.today(),
            applicator=self.app_tandem_only,
            image_guidance=self.guidance,
            tandem_length_cm=6.0,
            is_approved=True,
            approval_locked=True
        )
        session.approved_rules = session.get_rules_snapshot()
        session.save()

        # Admin changes the active rule in ApplicatorFieldRule
        tandem_def = ApplicatorMeasurementDefinition.objects.get(code='tandem_length_cm')
        rule = ApplicatorFieldRule.objects.get(
            applicator_type=self.app_tandem_only,
            measurement_definition=tandem_def
        )
        rule.min_value_override = 10.0  # Would fail session's 6.0 if applied dynamically
        rule.save()

        # The approved historical session preserves its snapshot and is not affected
        saved_snapshot = session.get_applicable_rules()
        self.assertTrue(session.approval_locked)
        # Form submission against locked session is blocked
        form = BrachySessionForm(data={'session_number': 1}, instance=session)
        self.assertFalse(form.is_valid())
        self.assertIn('locked against editing', str(form.errors))

        # Reset rule
        rule.min_value_override = None
        rule.save()

    def test_14_missing_measurements_cannot_be_completed_or_approved(self):
        """14. A record with missing applicator measurements cannot be completed or approved."""
        # 14a. Form completion rejected
        form = BrachySessionForm(data={
            'session_number': 1,
            'session_date': date.today(),
            'applicator': self.app_tandem_ovoids.id,
            'image_guidance': self.guidance.guidance_id,
            'session_status': self.status_completed.status_id,
            'tandem_length_cm': 6.0,
            # Missing ovoid_diameter_mm and ovoid_length_mm
        })
        self.assertFalse(form.is_valid())
        self.assertIn('ovoid_diameter_mm', form.errors)

        # 14b. Course approval rejected via treatment_approve_toggle
        incomplete_session = BrachySession.objects.create(
            brachy_course=self.course,
            session_number=1,
            session_date=date.today(),
            applicator=self.app_tandem_ovoids,
            image_guidance=self.guidance,
            tandem_length_cm=6.0
            # ovoid dia and len missing
        )
        c = Client()
        c.force_login(self.admin_user)
        approve_url = reverse('treatment_approve_toggle', kwargs={
            'course_type': 'brachy',
            'course_id': self.course.brachy_course_id
        })
        resp = c.post(approve_url, {
            'action_type': 'approve',
            'password': 'Password@123'
        }, follow=True)

        self.course.refresh_from_db()
        self.assertFalse(self.course.is_approved)

    def test_15_users_without_administrative_permission_cannot_edit_mapping(self):
        """15. Users without administrative permission cannot edit the mapping."""
        c = Client()
        c.force_login(self.clinical_user)
        admin_url = reverse('applicator_rules_admin')
        resp_get = c.get(admin_url, follow=True)
        # Non-admin user is redirected to dashboard with an error message
        self.assertIn('Permission Denied', resp_get.content.decode('utf-8'))

        # Post attempt by non-admin is blocked
        resp_post = c.post(admin_url, {'action': 'save_rules'}, follow=True)
        self.assertIn('Permission Denied', resp_post.content.decode('utf-8'))

        # Admin user CAN access
        c_admin = Client()
        c_admin.force_login(self.admin_user)
        resp_admin = c_admin.get(admin_url)
        self.assertEqual(resp_admin.status_code, 200)
        self.assertIn('Applicator Type Field Activation', resp_admin.content.decode('utf-8'))
