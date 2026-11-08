from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import date

from patients.models import Patient
from core.models import AuditLog
from followup.models import (
    FollowUpStatus, FollowUpContactType, ProxyStatus, DiseaseStatus,
    RecurrenceSite, CauseOfDeath, FollowUpInvestigationLink
)
from systemic.models import ResponseStatus
from clinical.models import Encounter, EncounterType, ECOGScore
from clinical.svg_generator import auto_populate_svg_from_encounter


@login_required
def followup_list_view(request, mr_no):
    """Replicates frmFollowUpList - Longitudinal surveillance tracking and survival timeline."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    followups = patient.follow_up_records.filter(soft_deleted=False).select_related(
        'disease_status', 'contact_type', 'recurrence_site', 'cause_of_death', 'encounter'
    ).prefetch_related('recurrence_sites', 'investigation_links', 'encounter__svg_findings')

    return render(request, 'followup/followup_list.html', {
        'patient': patient,
        'followups': followups,
    })


@login_required
def followup_form_view(request, mr_no, followup_id=None):
    """Replicates frmFollowUpStatus - Longitudinal visit encounter, recurrence detection & survival status."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    fu = get_object_or_404(FollowUpStatus, follow_up_status_id=followup_id, patient=patient) if followup_id else None

    contact_types = FollowUpContactType.objects.filter(is_active=True)
    proxy_statuses = ProxyStatus.objects.filter(is_active=True)
    disease_statuses = DiseaseStatus.objects.filter(is_active=True)
    response_statuses = ResponseStatus.objects.filter(is_active=True)
    recurrence_sites = RecurrenceSite.objects.filter(is_active=True)
    causes_of_death = CauseOfDeath.objects.filter(is_active=True)
    ecog_scores = ECOGScore.objects.filter(is_active=True)

    # Encounter & SVG Findings
    encounter = fu.encounter if (fu and fu.encounter) else None
    svg_findings = encounter.svg_findings.filter(soft_deleted=False) if encounter else []

    # Patient Investigations
    blood_tests = patient.blood_tests.filter(soft_deleted=False).order_by('-test_date')[:10]
    pathology_reports = patient.pathology_reports.filter(soft_deleted=False).order_by('-path_date')[:10]
    imaging_studies = patient.imaging_studies.filter(soft_deleted=False).order_by('-imaging_date')[:10]
    molecular_tests = patient.molecular_tests.filter(soft_deleted=False).order_by('-test_date')[:10]

    linked_investigation_keys = set()
    if fu:
        for link in fu.investigation_links.all():
            linked_investigation_keys.add(f"{link.investigation_type}_{link.investigation_id}")

    if request.method == 'POST':
        if not fu:
            fu = FollowUpStatus(patient=patient, entered_by=request.user.username)

        fu.follow_up_date = request.POST.get('follow_up_date') or date.today()
        fu.contact_type_id = request.POST.get('contact_type_id') or None

        # Rule 1: Only if contact type is "Proxy" - make proxy status active
        ct = FollowUpContactType.objects.filter(pk=fu.contact_type_id).first() if fu.contact_type_id else None
        is_proxy = ct and ('proxy' in ct.contact_type.lower()) and ('lost' not in ct.contact_type.lower())
        if is_proxy:
            fu.proxy_status_id = request.POST.get('proxy_status_id') or None
        else:
            fu.proxy_status_id = None

        fu.disease_status_id = request.POST.get('disease_status_id') or None
        fu.response_status_id = request.POST.get('response_status_id') or None

        ds = DiseaseStatus.objects.filter(pk=fu.disease_status_id).first() if fu.disease_status_id else None
        ds_name = ds.status_name.lower() if ds else ''
        ct_name = ct.contact_type.lower() if ct else ''

        # Determine dead & lost status
        is_dead = bool(request.POST.get('death_reported')) or ('dead' in ds_name)
        is_lost = ('lost' in ds_name) or ('lost' in ct_name)

        # Recurrence
        fu.recurrence_detected = bool(request.POST.get('recurrence_detected'))
        fu.date_of_recurrence = request.POST.get('date_of_recurrence') or None
        fu.recurrence_confirmed_by = request.POST.get('recurrence_confirmed_by', '')
        fu.recurrence_local = bool(request.POST.get('recurrence_local'))
        fu.recurrence_nodal = bool(request.POST.get('recurrence_nodal'))
        fu.recurrence_distant = bool(request.POST.get('recurrence_distant'))
        fu.second_primary = bool(request.POST.get('second_primary'))

        fu.node_pelvic = bool(request.POST.get('node_pelvic'))
        fu.node_para_aortic = bool(request.POST.get('node_para_aortic'))
        fu.node_inguinal = bool(request.POST.get('node_inguinal'))
        fu.distant_nodal_other = bool(request.POST.get('distant_nodal_other'))
        fu.distant_visceral = bool(request.POST.get('distant_visceral'))

        # Rule 2: Primary recurrence site multi-selection
        rec_site_ids = request.POST.getlist('recurrence_site_ids')
        if not rec_site_ids and request.POST.get('recurrence_site_id'):
            rec_site_ids = [request.POST.get('recurrence_site_id')]
        fu.recurrence_site_id = int(rec_site_ids[0]) if rec_site_ids else None
        fu.recurrence_treatment_plan = request.POST.get('recurrence_treatment_plan', '')

        # Rule 3: Only if patient is marked death should date of death be active
        if is_dead:
            fu.death_reported = True
            fu.date_of_death = request.POST.get('date_of_death') or None
            fu.cause_of_death_id = request.POST.get('cause_of_death_id') or None
        else:
            fu.death_reported = False
            fu.date_of_death = None
            fu.cause_of_death_id = None

        # Rule 4: For lost to follow up and dead - no need to make "Next scheduled follow-up date" active
        if is_dead or is_lost:
            fu.next_fu_date = None
            fu.next_fu_notes = ''
        else:
            fu.next_fu_date = request.POST.get('next_fu_date') or None
            fu.next_fu_notes = request.POST.get('next_fu_notes', '')

        fu.performance_notes = request.POST.get('performance_notes', '')
        fu.last_modified_by = request.user.username
        fu.save()

        # Update M2M recurrence sites
        if rec_site_ids:
            fu.recurrence_sites.set(rec_site_ids)
        else:
            fu.recurrence_sites.clear()

        # Rule 5: In case of patients other than Dead and lost to follow-up - clinical examination findings & investigations
        if not (is_dead or is_lost):
            # Clinical Encounter & Physical Exam
            enc = fu.encounter
            if not enc:
                enc_type_fu = EncounterType.objects.filter(encounter_type_name__icontains='Follow-up').first()
                if not enc_type_fu:
                    enc_type_fu = EncounterType.objects.first()
                enc = Encounter(patient=patient, encounter_type=enc_type_fu, entered_by=request.user.username)

            enc.encounter_date = fu.follow_up_date
            enc.ecog_id = request.POST.get('exam_ecog_id') or None
            enc.presenting_complaints = request.POST.get('exam_presenting_complaints', '')
            enc.examination_findings = request.POST.get('exam_examination_findings', '')

            # Pelvic Exam
            enc.parametrial_invasion = bool(request.POST.get('exam_parametrial_invasion'))
            enc.para_left = bool(request.POST.get('exam_para_left'))
            enc.para_right = bool(request.POST.get('exam_para_right'))
            enc.para_extent_left_cm = float(request.POST.get('exam_para_extent_left_cm')) if request.POST.get('exam_para_extent_left_cm') else None
            enc.para_extent_right_cm = float(request.POST.get('exam_para_extent_right_cm')) if request.POST.get('exam_para_extent_right_cm') else None

            enc.rectal_invasion = bool(request.POST.get('exam_rectal_invasion'))
            enc.bladder_invasion = bool(request.POST.get('exam_bladder_invasion'))

            enc.tumour_size_cm = float(request.POST.get('exam_tumour_size_cm')) if request.POST.get('exam_tumour_size_cm') else None
            enc.tumour_size_2_cm = float(request.POST.get('exam_tumour_size_2_cm')) if request.POST.get('exam_tumour_size_2_cm') else None
            enc.tumour_size_3_cm = float(request.POST.get('exam_tumour_size_3_cm')) if request.POST.get('exam_tumour_size_3_cm') else None
            enc.last_modified_by = request.user.username
            enc.save()

            fu.encounter = enc
            fu.save(update_fields=['encounter'])

            # Auto-populate SVG if requested
            if bool(request.POST.get('auto_populate_svg')):
                auto_populate_svg_from_encounter(enc, user_username=request.user.username, force_overwrite=True)
                messages.info(request, "Auto-populated IBS anatomical pelvic diagram from physical examination findings.")

            # Update Investigation Links
            FollowUpInvestigationLink.objects.filter(follow_up=fu).delete()
            for b_id in request.POST.getlist('link_blood_ids'):
                FollowUpInvestigationLink.objects.create(follow_up=fu, investigation_type='Blood', investigation_id=int(b_id))
            for img_id in request.POST.getlist('link_imaging_ids'):
                FollowUpInvestigationLink.objects.create(follow_up=fu, investigation_type='Imaging', investigation_id=int(img_id))
            for p_id in request.POST.getlist('link_pathology_ids'):
                FollowUpInvestigationLink.objects.create(follow_up=fu, investigation_type='Pathology', investigation_id=int(p_id))
            for m_id in request.POST.getlist('link_molecular_ids'):
                FollowUpInvestigationLink.objects.create(follow_up=fu, investigation_type='Molecular', investigation_id=int(m_id))

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="UPDATE" if followup_id else "INSERT",
            table_affected="tblFollowUpStatus",
            record_ref=f"{patient.mr_no}-FU#{fu.follow_up_status_id}",
            notes=f"Saved follow-up visit: {fu.disease_status}"
        )

        messages.success(request, f"Follow-up visit record ({fu.follow_up_date}) saved.")

        # Quick navigation handling
        if 'open_diagram' in request.POST and fu.encounter:
            return redirect(f"/clinical/encounter/{fu.encounter.clinical_id}/diagram/?return_to=followup&fu_id={fu.follow_up_status_id}")
        if 'open_blood_add' in request.POST:
            return redirect(f"/investigations/{patient.mr_no}/blood/add/?return_to=followup&fu_id={fu.follow_up_status_id}")
        if 'open_imaging_add' in request.POST:
            return redirect(f"/investigations/{patient.mr_no}/imaging/add/?return_to=followup&fu_id={fu.follow_up_status_id}")
        if 'open_pathology_add' in request.POST:
            return redirect(f"/investigations/{patient.mr_no}/pathology/add/?return_to=followup&fu_id={fu.follow_up_status_id}")
        if 'open_molecular_add' in request.POST:
            return redirect(f"/investigations/{patient.mr_no}/molecular/add/?return_to=followup&fu_id={fu.follow_up_status_id}")

        if 'save_patient_dashboard' in request.POST:
            return redirect('patient_dashboard', mr_no=patient.mr_no)
        if 'save_next' in request.POST:
            return redirect('patient_summary', mr_no=patient.mr_no)
        if 'save_stay' in request.POST:
            return redirect('followup_edit', mr_no=patient.mr_no, followup_id=fu.follow_up_status_id)
        return redirect('followup_list', mr_no=patient.mr_no)

    # Pre-select recurrence site IDs for form template
    selected_rec_site_ids = set()
    if fu:
        selected_rec_site_ids = set(fu.recurrence_sites.values_list('recurrence_site_id', flat=True))
        if fu.recurrence_site_id:
            selected_rec_site_ids.add(fu.recurrence_site_id)

    return render(request, 'followup/followup_form.html', {
        'patient': patient,
        'fu': fu,
        'encounter': encounter,
        'svg_findings': svg_findings,
        'contact_types': contact_types,
        'proxy_statuses': proxy_statuses,
        'disease_statuses': disease_statuses,
        'response_statuses': response_statuses,
        'recurrence_sites': recurrence_sites,
        'selected_rec_site_ids': selected_rec_site_ids,
        'causes_of_death': causes_of_death,
        'ecog_scores': ecog_scores,
        'blood_tests': blood_tests,
        'pathology_reports': pathology_reports,
        'imaging_studies': imaging_studies,
        'molecular_tests': molecular_tests,
        'linked_investigation_keys': linked_investigation_keys,
    })


@login_required
def followup_delete_view(request, mr_no, followup_id):
    """Allows administrators to delete (soft-delete) a specific follow-up entry."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Permission denied: Administrator privileges required to delete follow-up records.")
        return redirect('followup_list', mr_no=mr_no)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    fu = get_object_or_404(FollowUpStatus, follow_up_status_id=followup_id, patient=patient)

    if request.method == 'POST':
        fu_date = fu.follow_up_date
        fu.soft_deleted = True
        fu.save()

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="DELETE",
            table_affected="tblFollowUpStatus",
            record_ref=f"{patient.mr_no}-FU#{followup_id}",
            notes=f"Soft-deleted follow-up visit on {fu_date}"
        )

        messages.success(request, f"Follow-up entry for {fu_date} deleted successfully.")
        return redirect('followup_list', mr_no=patient.mr_no)

    return redirect('followup_list', mr_no=patient.mr_no)
