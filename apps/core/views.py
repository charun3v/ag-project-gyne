import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils import timezone
from django.db.models import Count

from core.models import ApprovalAudit, AuditLog
from patients.models import Patient
from clinical.models import Diagnosis, Encounter, ClinicalHistory
from radiotherapy.models import EBRTCourse, BrachyCourse
from systemic.models import NACTCourse, AdjuvantChemoCourse
from investigations.models import BloodInvestigation, ImagingInvestigation, PathologyInvestigation, MolecularInvestigation
from followup.models import FollowUpStatus
from documents.models import PatientDocument

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        u = request.POST.get('username', '').strip()
        p = request.POST.get('password', '').strip()
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password. Please verify credentials.")
    return render(request, 'core/login.html')

def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')

@login_required
def dashboard_view(request, mr_no=None):
    """
    Central clinical dashboard replicating frmDashboard and continuous frmDashboardPatientRow.
    Computes status badges for each of the 11 workflow tiles per patient.
    If mr_no is specified, serves the Patient-Specific Dashboard for that single patient.
    """
    if not mr_no:
        mr_no = request.GET.get('mr_no')

    patients_qs = Patient.objects.filter(soft_deleted=False).prefetch_related(
        'diagnoses__primary_site', 'encounters__encounter_type', 'histories',
        'ebrt_courses__course_status', 'brachy_courses__course_status',
        'nact_courses__nact_status', 'adjuvant_courses__chemo_status',
        'follow_up_records__disease_status', 'documents',
        'blood_tests', 'imaging_studies', 'pathology_reports', 'molecular_tests'
    )

    single_patient = None
    is_single_patient = False
    if mr_no:
        single_patient = get_object_or_404(Patient, mr_no=mr_no, soft_deleted=False)
        patients_qs = patients_qs.filter(mr_no=mr_no)
        is_single_patient = True

    patients_data = []
    for pt in patients_qs:
        # Demographics: Complete if phone, age/dob, and address/district present
        demographics_completed = bool(pt.phone and (pt.date_of_birth or pt.age) and (pt.address or pt.district or pt.state))
        demographics_tile_class = 'tile-done' if demographics_completed else 'tile-partial'
        demographics_status_text = '✓ Done' if demographics_completed else 'Edit'

        # Diagnosis
        diag_list = list(pt.diagnoses.filter(soft_deleted=False).order_by('-is_current', 'diagnosis_sequence', '-date_of_diagnosis'))
        curr_diag = diag_list[0] if diag_list else None
        diag_count = len(diag_list)
        site_name = curr_diag.primary_site.site if (curr_diag and curr_diag.primary_site) else "Gynae Oncology"
        stage_text = curr_diag.stage_text if curr_diag else ""
        all_diag_desc = "; ".join([d.diagnosis_description or (f"{d.primary_site.site if d.primary_site else 'Cancer'} Stage {d.stage_text or '—'}") for d in diag_list])

        if not curr_diag:
            diagnosis_tile_class = ''
            diagnosis_status_text = '—'
        else:
            diagnosis_completed = bool(curr_diag.primary_site and curr_diag.stage_text and curr_diag.histology)
            diagnosis_tile_class = 'tile-done' if diagnosis_completed else 'tile-partial'
            if diagnosis_completed:
                diagnosis_status_text = f"✓ {diag_count} Diag" if diag_count > 1 else f"✓ Stage {stage_text or 'Done'}"
            else:
                diagnosis_status_text = 'Incomplete'

        # History
        hist_list = list(pt.histories.filter(soft_deleted=False).order_by('-snapshot_date'))
        curr_hist = hist_list[0] if hist_list else None
        if not curr_hist:
            history_tile_class = ''
            history_status_text = '—'
        else:
            history_completed = bool(
                curr_hist.bleeding_pv or curr_hist.water_discharge_pv or curr_hist.dyspareunia or curr_hist.loin_pain or
                curr_hist.hpi or curr_hist.hypertension or curr_hist.hypothyroidism or curr_hist.diabetic or
                curr_hist.seizures or curr_hist.past_med_surg or curr_hist.smoking or curr_hist.tobacco_chewing or
                curr_hist.prior_radiation or curr_hist.previous_surgery or curr_hist.comorbidity_notes
            )
            history_tile_class = 'tile-done' if history_completed else 'tile-partial'
            history_status_text = '✓ Done' if history_completed else 'Incomplete'

        # Baseline Exam
        base_enc = pt.encounters.filter(encounter_type__encounter_type_name__icontains='Baseline', soft_deleted=False).first()
        if not base_enc:
            baseline_exam_tile_class = ''
            baseline_exam_status_text = '—'
        else:
            base_completed = bool(base_enc.tumour_size_cm is not None or base_enc.examination_findings or base_enc.findings_locked or base_enc.parametrial_invasion)
            baseline_exam_tile_class = 'tile-done' if base_completed else 'tile-partial'
            baseline_exam_status_text = f"✓ {base_enc.encounter_date.strftime('%d %b')}" if base_completed else 'Incomplete'

        # Pre-Brachy Exam
        preb_enc = pt.encounters.filter(encounter_type__encounter_type_name__icontains='Pre-Brachy', soft_deleted=False).first()
        if not preb_enc:
            prebrachy_exam_tile_class = ''
            prebrachy_exam_status_text = '—'
        else:
            preb_completed = bool(preb_enc.tumour_size_cm is not None or preb_enc.examination_findings or preb_enc.findings_locked or preb_enc.tandem_sounded)
            prebrachy_exam_tile_class = 'tile-done' if preb_completed else 'tile-partial'
            prebrachy_exam_status_text = '✓ Done' if preb_completed else 'Incomplete'

        # Post-NACT Exam
        postnact_enc = pt.encounters.filter(encounter_type__encounter_type_name__icontains='Post-NACT', soft_deleted=False).first()
        if not postnact_enc:
            postnact_exam_tile_class = ''
        else:
            postnact_completed = bool(postnact_enc.tumour_size_cm is not None or postnact_enc.examination_findings or postnact_enc.findings_locked)
            postnact_exam_tile_class = 'tile-done' if postnact_completed else 'tile-partial'

        # Investigations
        has_blood = pt.blood_tests.filter(soft_deleted=False).exists()
        has_img = pt.imaging_studies.filter(soft_deleted=False).exists()
        has_path = pt.pathology_reports.filter(soft_deleted=False).exists()
        has_mol = pt.molecular_tests.filter(soft_deleted=False).exists()
        has_inv = has_blood or has_img or has_path or has_mol
        if not has_inv:
            investigations_tile_class = ''
            investigations_status_text = '—'
        else:
            inv_completed = bool(has_blood and has_img and has_path)
            investigations_tile_class = 'tile-done' if inv_completed else 'tile-partial'
            investigations_status_text = '✓ Complete' if inv_completed else 'Partial'

        # Treatments
        # NACT
        nact = pt.nact_courses.filter(soft_deleted=False).first()
        if not nact or not nact.nact_received:
            nact_tile_class = ''
            nact_status_text = '—'
        else:
            nact_completed = bool(nact.nact_status and nact.nact_status.status_name and nact.nact_status.status_name.lower() == 'complete')
            nact_tile_class = 'tile-done' if nact_completed else 'tile-partial'
            nact_status_text = '✓ Complete' if nact_completed else ('Incomplete' if (nact.nact_status and 'incom' in nact.nact_status.status_name.lower()) else 'Active')

        # EBRT
        ebrt = pt.ebrt_courses.filter(soft_deleted=False).first()
        if not ebrt:
            ebrt_tile_class = ''
            ebrt_status_text = '—'
        else:
            ebrt_completed = bool(ebrt.treatment_completed or (ebrt.course_status and ebrt.course_status.status_name and ebrt.course_status.status_name.lower() == 'completed'))
            ebrt_tile_class = 'tile-done' if ebrt_completed else 'tile-partial'
            ebrt_status_text = f"✓ {ebrt.total_dose_gy or 0}Gy" if ebrt_completed else f"{ebrt.total_dose_gy or 0}Gy Incomplete"

        # Brachytherapy
        brachy = pt.brachy_courses.filter(soft_deleted=False).first()
        if not brachy or not brachy.brachy_received:
            brachy_tile_class = ''
            brachy_status_text = '—'
        else:
            brachy_completed = bool((brachy.completion_status and brachy.completion_status.lower() == 'completed') or (brachy.course_status and brachy.course_status.status_name and brachy.course_status.status_name.lower() == 'completed'))
            brachy_tile_class = 'tile-done' if brachy_completed else 'tile-partial'
            brachy_status_text = f"✓ {brachy.total_fractions_delivered or 0} Fx" if brachy_completed else f"{brachy.total_fractions_delivered or 0} Fx Incomplete"

        # Adjuvant Chemotherapy
        adjuvant = pt.adjuvant_courses.filter(soft_deleted=False).first() if hasattr(pt.adjuvant_courses, 'filter') else pt.adjuvant_courses.first()
        if not adjuvant or not adjuvant.adjuvant_received:
            adjuvant_tile_class = ''
            adjuvant_status_text = '—'
        else:
            adjuvant_completed = bool(adjuvant.chemo_status and adjuvant.chemo_status.status_name and adjuvant.chemo_status.status_name.lower() == 'complete')
            adjuvant_tile_class = 'tile-done' if adjuvant_completed else 'tile-partial'
            adjuvant_status_text = '✓ Complete' if adjuvant_completed else ('Incomplete' if (adjuvant.chemo_status and 'incom' in adjuvant.chemo_status.status_name.lower()) else 'Active')

        # Follow-Up (User rule: except follow-up, which becomes green if logged!)
        last_fu = pt.follow_up_records.filter(soft_deleted=False).first()
        fu_status_str = last_fu.disease_status.status_name if (last_fu and last_fu.disease_status) else ""
        if last_fu:
            followup_tile_class = 'tile-done'  # Green exception!
            followup_status_text = f"✓ {fu_status_str or 'Logged'}"
        else:
            followup_tile_class = ''
            followup_status_text = '—'

        # Documents
        doc_count = pt.documents.count()

        patients_data.append({
            'mr_no': pt.mr_no,
            'pt_name': pt.pt_name,
            'sex': pt.sex,
            'age': pt.age,
            'site_badge': site_name,
            'has_demographics': bool(pt.phone and pt.country),
            'has_diagnosis': bool(curr_diag),
            'diag_count': diag_count,
            'stage_text': stage_text,
            'all_diag_desc': all_diag_desc,
            'has_history': bool(curr_hist),
            'has_baseline_exam': bool(base_enc),
            'baseline_exam_date': base_enc.encounter_date if base_enc else None,
            'has_prebrachy_exam': bool(preb_enc),
            'has_postnact_exam': bool(postnact_enc),
            'has_investigations': has_inv,
            'has_nact': bool(nact and nact.nact_received),
            'has_ebrt': bool(ebrt),
            'ebrt_dose': ebrt.total_dose_gy if ebrt else 0,
            'has_brachy': bool(brachy and brachy.brachy_received),
            'brachy_fx_count': brachy.total_fractions_delivered if brachy else 0,
            'has_adjuvant': bool(adjuvant and adjuvant.adjuvant_received),
            'has_followup': bool(last_fu),
            'last_fu_status': fu_status_str or ("Logged" if last_fu else ""),
            'document_count': doc_count,

            # Status Classes & Labels
            'demographics_tile_class': demographics_tile_class,
            'demographics_status_text': demographics_status_text,
            'history_tile_class': history_tile_class,
            'history_status_text': history_status_text,
            'baseline_exam_tile_class': baseline_exam_tile_class,
            'baseline_exam_status_text': baseline_exam_status_text,
            'prebrachy_exam_tile_class': prebrachy_exam_tile_class,
            'prebrachy_exam_status_text': prebrachy_exam_status_text,
            'postnact_exam_tile_class': postnact_exam_tile_class,
            'investigations_tile_class': investigations_tile_class,
            'investigations_status_text': investigations_status_text,
            'diagnosis_tile_class': diagnosis_tile_class,
            'diagnosis_status_text': diagnosis_status_text,
            'nact_tile_class': nact_tile_class,
            'nact_status_text': nact_status_text,
            'ebrt_tile_class': ebrt_tile_class,
            'ebrt_status_text': ebrt_status_text,
            'brachy_tile_class': brachy_tile_class,
            'brachy_status_text': brachy_status_text,
            'adjuvant_tile_class': adjuvant_tile_class,
            'adjuvant_status_text': adjuvant_status_text,
            'followup_tile_class': followup_tile_class,
            'followup_status_text': followup_status_text,
        })

    return render(request, 'core/dashboard.html', {
        'patients': patients_data,
        'single_patient': single_patient,
        'is_single_patient': is_single_patient,
    })


@login_required
def patient_dashboard_view(request, mr_no):
    """Serves the Patient-Specific Dashboard for a single patient."""
    return dashboard_view(request, mr_no=mr_no)

@login_required
def export_data_view(request):
    """
    Generates Analytical Research Exports matching the specification:
    - Wide-format (default): One row per patient with descriptive text names (no IDs or internal audit stamps).
    - Long-format (?format=long): One row per event or drug administration for longitudinal/timeline analysis in R.
    """
    export_format = request.GET.get('format', 'wide').lower()

    if export_format == 'long':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="gynae_oncology_long_format_events.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'MR_No', 'Patient_Name', 'Phase', 'Course_ID', 'Cycle_Number', 'Event_Date',
            'Drug_Agent', 'Dose', 'Dose_Unit', 'No_Of_Days', 'Day_Of_Administration',
            'Route', 'Administered', 'Status', 'Approval_Status'
        ])

        for pt in Patient.objects.filter(soft_deleted=False).prefetch_related(
            'nact_courses__cycles__drugs__chemo_agent',
            'nact_courses__cycles__drugs__dose_unit',
            'nact_courses__cycles__drugs__chemo_route',
            'ebrt_courses__concurrent_chemo_courses__cycles__drugs__chemo_agent',
            'ebrt_courses__concurrent_chemo_courses__cycles__drugs__dose_unit',
            'ebrt_courses__concurrent_chemo_courses__cycles__drugs__chemo_route',
            'adjuvant_courses__cycles__drugs__chemo_agent',
            'adjuvant_courses__cycles__drugs__dose_unit',
            'adjuvant_courses__cycles__drugs__chemo_route'
        ):
            # NACT Events
            for nact in pt.nact_courses.filter(nact_received=True):
                appr_str = f"Approved by {nact.approved_by}" if nact.is_approved else "Draft"
                for cyc in nact.cycles.all():
                    for d in cyc.drugs.all():
                        writer.writerow([
                            pt.mr_no, pt.pt_name, 'NACT', nact.nact_course_id, cyc.cycle_number,
                            cyc.cycle_date, d.chemo_agent.agent_name, d.dose,
                            d.dose_unit.unit_name if d.dose_unit else '',
                            d.no_of_days, d.day_of_administration,
                            d.chemo_route.route_name if d.chemo_route else '',
                            'Yes' if d.administered else 'No',
                            cyc.cycle_status, appr_str
                        ])

            # Concurrent Chemo Events
            for ebrt in pt.ebrt_courses.all():
                ebrt_appr = f"Approved by {ebrt.approved_by}" if ebrt.is_approved else "Draft"
                for conc in ebrt.concurrent_chemo_courses.filter(concurrent_received=True):
                    for cyc in conc.cycles.all():
                        for d in cyc.drugs.all():
                            writer.writerow([
                                pt.mr_no, pt.pt_name, 'Concurrent_Chemo', ebrt.ebrt_course_id, cyc.cycle_number,
                                cyc.cycle_date, d.chemo_agent.agent_name, d.dose,
                                d.dose_unit.unit_name if d.dose_unit else '',
                                d.no_of_days, d.day_of_administration,
                                d.chemo_route.route_name if d.chemo_route else '',
                                'Yes' if d.administered else 'No',
                                cyc.cycle_status, ebrt_appr
                            ])

            # Adjuvant Events
            for adj in pt.adjuvant_courses.filter(adjuvant_received=True):
                adj_appr = f"Approved by {adj.approved_by}" if adj.is_approved else "Draft"
                for cyc in adj.cycles.all():
                    for d in cyc.drugs.all():
                        writer.writerow([
                            pt.mr_no, pt.pt_name, 'Adjuvant_Chemo', adj.adjuvant_course_id, cyc.cycle_number,
                            cyc.cycle_date, d.chemo_agent.agent_name, d.dose,
                            d.dose_unit.unit_name if d.dose_unit else '',
                            d.no_of_days, d.day_of_administration,
                            d.chemo_route.route_name if d.chemo_route else '',
                            'Yes' if d.administered else 'No',
                            cyc.cycle_status, adj_appr
                        ])

        return response

    # Default: Wide-Format Patient-Level Analytical Record
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="gynae_oncology_wide_format_patients.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'MR_No', 'Patient_Name', 'Age', 'Sex', 'Date_Of_Birth', 'Registration_Date',
        'Primary_Consultant', 'Primary_Site', 'Histology', 'FIGO_Stage', 'ECOG_Score',
        'NACT_Given', 'NACT_Regimen', 'NACT_Planned_Cycles', 'NACT_Received_Cycles',
        'NACT_Response', 'NACT_Status', 'NACT_Approved',
        'EBRT_Given', 'EBRT_Intent', 'EBRT_Technique', 'EBRT_Targets',
        'EBRT_Total_Dose_Gy', 'EBRT_Fractions', 'EBRT_Start_Date', 'EBRT_End_Date',
        'EBRT_Status', 'EBRT_Approved',
        'Concurrent_Chemo_Given', 'Concurrent_Regimen', 'Concurrent_Cycles_Administered',
        'Brachy_Given', 'Brachy_Source', 'Brachy_Dosing', 'Brachy_Prescription_Dose_Gy',
        'Brachy_Fractions_Delivered', 'Brachy_Status', 'Brachy_Approved',
        'Adjuvant_Chemo_Given', 'Adjuvant_Planned_Cycles', 'Adjuvant_Received_Cycles',
        'Adjuvant_Status', 'Adjuvant_Approved', 'FollowUp_Status'
    ])

    for pt in Patient.objects.filter(soft_deleted=False).prefetch_related(
        'diagnoses__primary_site', 'diagnoses__histology', 'encounters__ecog',
        'nact_courses__chemo_regimen', 'nact_courses__response_to_nact', 'nact_courses__nact_status',
        'ebrt_courses__ebrt_intent', 'ebrt_courses__ebrt_technique', 'ebrt_courses__sites__ebrt_site',
        'ebrt_courses__concurrent_chemo_courses', 'brachy_courses__brachy_source', 'brachy_courses__brachy_dosing',
        'adjuvant_courses__chemo_status', 'follow_up_records__disease_status'
    ):
        diag = pt.diagnoses.filter(is_current=True).first()
        base_enc = pt.encounters.filter(encounter_type__encounter_type_name__icontains='Baseline').first()
        nact = pt.nact_courses.first()
        ebrt = pt.ebrt_courses.first()
        conc = ebrt.concurrent_chemo_courses.first() if ebrt else None
        brachy = pt.brachy_courses.first()
        adj = pt.adjuvant_courses.first()
        fu = pt.follow_up_records.first()

        targets_str = ", ".join([s.ebrt_site.site_name for s in ebrt.sites.all()]) if ebrt else ''

        writer.writerow([
            pt.mr_no,
            pt.pt_name,
            pt.age or '',
            pt.sex,
            pt.date_of_birth or '',
            pt.date_of_registration or '',
            pt.primary_consultant.consultant_name if pt.primary_consultant else '',
            diag.primary_site.site if (diag and diag.primary_site) else '',
            diag.histology.histology_name if (diag and diag.histology) else '',
            diag.stage_text if diag else '',
            base_enc.ecog.score if (base_enc and base_enc.ecog) else '',
            'Yes' if (nact and nact.nact_received) else 'No',
            nact.chemo_regimen.regimen_code if (nact and nact.chemo_regimen) else '',
            nact.planned_cycles if nact else '',
            nact.cycles.count() if nact else '',
            nact.response_to_nact.response_code if (nact and nact.response_to_nact) else '',
            nact.nact_status.status_name if (nact and nact.nact_status) else '',
            'Yes' if (nact and nact.is_approved) else 'No',
            'Yes' if ebrt else 'No',
            ebrt.ebrt_intent.intent_name if (ebrt and ebrt.ebrt_intent) else '',
            ebrt.ebrt_technique.technique_name if (ebrt and ebrt.ebrt_technique) else '',
            targets_str,
            ebrt.total_dose_gy if (ebrt and ebrt.total_dose_gy) else '',
            ebrt.total_fractions if (ebrt and ebrt.total_fractions) else '',
            ebrt.ebrt_start_date if (ebrt and ebrt.ebrt_start_date) else '',
            ebrt.ebrt_end_date if (ebrt and ebrt.ebrt_end_date) else '',
            ebrt.course_status.status_name if (ebrt and ebrt.course_status) else '',
            'Yes' if (ebrt and ebrt.is_approved) else 'No',
            'Yes' if (conc and conc.concurrent_received) else 'No',
            conc.chemo_regimen.regimen_code if (conc and conc.chemo_regimen) else '',
            conc.cycles.count() if conc else '',
            'Yes' if brachy else 'No',
            brachy.brachy_source.source_name if (brachy and brachy.brachy_source) else '',
            brachy.brachy_dosing.dosing_point if (brachy and brachy.brachy_dosing) else '',
            brachy.prescription_dose_gy if brachy else '',
            brachy.total_fractions_delivered if brachy else '',
            brachy.completion_status if brachy else '',
            'Yes' if (brachy and brachy.is_approved) else 'No',
            'Yes' if (adj and adj.adjuvant_received) else 'No',
            adj.planned_cycles if adj else '',
            adj.cycles.count() if adj else '',
            adj.chemo_status.status_name if (adj and adj.chemo_status) else '',
            'Yes' if (adj and adj.is_approved) else 'No',
            fu.disease_status.status_name if (fu and fu.disease_status) else '',
        ])

    return response


# --- Admin User Management & Access Control ---

def is_admin_user(user):
    """Checks if the user has administrative privileges or cap_manage_users."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    profile = getattr(user, 'profile', None)
    if profile and profile.role and profile.role.cap_manage_users:
        return True
    return False

@login_required
def user_list_view(request):
    """Replicates Access User Management - lists all system users and roles."""
    if not is_admin_user(request.user):
        messages.error(request, "Access denied. User Management requires administrator privileges.")
        return redirect('dashboard')

    from django.contrib.auth.models import User
    from core.models import Role, UserProfile

    users = User.objects.all().select_related('profile__role').order_by('username')
    roles = Role.objects.filter(is_active=True)

    return render(request, 'core/user_list.html', {
        'users': users,
        'roles': roles,
    })

@login_required
def user_form_view(request, user_id=None):
    """Create or edit system user accounts."""
    if not is_admin_user(request.user):
        messages.error(request, "Access denied. User Management requires administrator privileges.")
        return redirect('dashboard')

    from django.contrib.auth.models import User
    from core.models import Role, UserProfile, AuditLog

    edit_user = get_object_or_404(User, id=user_id) if user_id else None
    roles = Role.objects.filter(is_active=True)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        role_id = request.POST.get('role_id')
        is_active = bool(request.POST.get('is_active'))
        is_staff = bool(request.POST.get('is_staff'))

        if not edit_user:
            if not username or not password:
                messages.error(request, "Username and Password are required to create a new user.")
                return render(request, 'core/user_form.html', {'roles': roles, 'edit_user': edit_user})
            if User.objects.filter(username=username).exists():
                messages.error(request, f"User with username '{username}' already exists.")
                return render(request, 'core/user_form.html', {'roles': roles, 'edit_user': edit_user})

            new_user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=is_active,
                is_staff=is_staff
            )
            role = Role.objects.filter(role_id=role_id).first() if role_id else None
            UserProfile.objects.create(user=new_user, role=role, user_level=role.role_name if role else 'Standard')

            AuditLog.objects.create(
                username=request.user.username,
                full_name=request.user.first_name,
                action="INSERT",
                table_affected="tblUsers",
                record_ref=f"User:{new_user.username}",
                notes=f"Created new user account with role '{role}'"
            )
            messages.success(request, f"User '{new_user.username}' created successfully.")
            return redirect('user_list')
        else:
            edit_user.first_name = first_name
            edit_user.last_name = last_name
            edit_user.email = email
            edit_user.is_active = is_active
            edit_user.is_staff = is_staff
            if password:
                edit_user.set_password(password)
            edit_user.save()

            role = Role.objects.filter(role_id=role_id).first() if role_id else None
            profile, _ = UserProfile.objects.get_or_create(user=edit_user)
            profile.role = role
            profile.user_level = role.role_name if role else 'Standard'
            profile.save()

            AuditLog.objects.create(
                username=request.user.username,
                full_name=request.user.first_name,
                action="UPDATE",
                table_affected="tblUsers",
                record_ref=f"User:{edit_user.username}",
                notes=f"Updated user account '{edit_user.username}'"
            )
            messages.success(request, f"User '{edit_user.username}' updated successfully.")
            return redirect('user_list')

    return render(request, 'core/user_form.html', {
        'edit_user': edit_user,
        'roles': roles,
    })

@login_required
def user_toggle_active_view(request, user_id):
    """Quickly activate or deactivate a user account."""
    if not is_admin_user(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    from django.contrib.auth.models import User
    from core.models import AuditLog

    target_user = get_object_or_404(User, id=user_id)
    if target_user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect('user_list')

    target_user.is_active = not target_user.is_active
    target_user.save()

    AuditLog.objects.create(
        username=request.user.username,
        full_name=request.user.first_name,
        action="UPDATE",
        table_affected="tblUsers",
        record_ref=f"User:{target_user.username}",
        notes=f"Toggled user active status to {target_user.is_active}"
    )
    messages.success(request, f"User '{target_user.username}' status set to {'Active' if target_user.is_active else 'Inactive'}.")
    return redirect('user_list')


# --- Centralized Dropdowns & Lookup Tables Manager ---

LOOKUP_CONFIG = {
    'source': {
        'title': 'Source & HDR Afterloader',
        'table_name': 'sbtblBrachySourceType',
        'app': 'radiotherapy',
        'model_name': 'BrachySourceType',
        'pk': 'source_id',
        'name_field': 'source_name',
        'name_label': 'Source Name / Afterloader Model',
        'secondary_field': None,
        'secondary_label': None,
    },
    'machine': {
        'title': 'EBRT Machines & Linacs',
        'table_name': 'sbtblRTMachine',
        'app': 'radiotherapy',
        'model_name': 'RTMachine',
        'pk': 'machine_id',
        'name_field': 'machine_name',
        'name_label': 'Machine / Linac Name',
        'secondary_field': None,
        'secondary_label': None,
    },
    'centre': {
        'title': 'Treatment Centres',
        'table_name': 'sbtblTreatmentCentre',
        'app': 'radiotherapy',
        'model_name': 'TreatmentCentre',
        'pk': 'centre_id',
        'name_field': 'centre_name',
        'name_label': 'Treatment Centre Name',
        'secondary_field': 'centre_code',
        'secondary_label': 'Centre Code',
    },
    'intent': {
        'title': 'Treatment Intent',
        'table_name': 'sbtblEBRTIntent',
        'app': 'radiotherapy',
        'model_name': 'EBRTIntent',
        'pk': 'intent_id',
        'name_field': 'intent_name',
        'name_label': 'Intent Name (e.g. Radical, Adjuvant, Palliative)',
        'secondary_field': None,
        'secondary_label': None,
    },
    'technique': {
        'title': 'EBRT Techniques',
        'table_name': 'sbtblEBRTechnique',
        'app': 'radiotherapy',
        'model_name': 'EBRTTechnique',
        'pk': 'technique_id',
        'name_field': 'technique_name',
        'name_label': 'Technique Name (e.g. VMAT, 3DCRT, IMRT)',
        'secondary_field': None,
        'secondary_label': None,
    },
    'dosing': {
        'title': 'Brachy Dosing Points',
        'table_name': 'sbtblBrachyDosing',
        'app': 'radiotherapy',
        'model_name': 'BrachyDosing',
        'pk': 'dosing_id',
        'name_field': 'dosing_point',
        'name_label': 'Prescription Dosing Point',
        'secondary_field': 'dosing_system',
        'secondary_label': 'Dosing System (e.g. Manchester, GEC-ESTRO)',
    },
    'applicator': {
        'title': 'Brachy Applicators',
        'table_name': 'sbtblBrachyApplicator',
        'app': 'radiotherapy',
        'model_name': 'ApplicatorType',
        'pk': 'id',
        'name_field': 'name',
        'name_label': 'Applicator Name (e.g. Fletcher Tandem & Ovoids)',
        'secondary_field': None,
        'secondary_label': None,
    },
    'guidance': {
        'title': 'Image Guidance Modalities',
        'table_name': 'sbtblBrachyImageGuidance',
        'app': 'radiotherapy',
        'model_name': 'BrachyImageGuidance',
        'pk': 'guidance_id',
        'name_field': 'guidance_name',
        'name_label': 'Guidance Name (e.g. CT, MRI, Ultrasound)',
        'secondary_field': None,
        'secondary_label': None,
    },
    'interruption': {
        'title': 'RT Interruption Reasons',
        'table_name': 'sbtblInterruptionReason',
        'app': 'radiotherapy',
        'model_name': 'InterruptionReason',
        'pk': 'reason_id',
        'name_field': 'reason_name',
        'name_label': 'Reason Name (e.g. Machine Breakdown, Toxicity)',
        'secondary_field': None,
        'secondary_label': None,
    },
    'site': {
        'title': 'Primary Cancer Sites',
        'table_name': 'sbtblPrimarysite',
        'app': 'clinical',
        'model_name': 'PrimarySite',
        'pk': 'site_id',
        'name_field': 'site',
        'name_label': 'Cancer Site (e.g. Cervix, Endometrium, Ovary)',
        'secondary_field': None,
        'secondary_label': None,
    },
    'histology': {
        'title': 'Histological Types',
        'table_name': 'sbtblHistology',
        'app': 'clinical',
        'model_name': 'Histology',
        'pk': 'histology_id',
        'name_field': 'histology_name',
        'name_label': 'Histology (e.g. Squamous Cell Carcinoma)',
        'secondary_field': None,
        'secondary_label': None,
    },
    'consultant': {
        'title': 'Primary Consultants',
        'table_name': 'tblConsultant',
        'app': 'core',
        'model_name': 'Consultant',
        'pk': 'consultant_id',
        'name_field': 'consultant_name',
        'name_label': 'Consultant Doctor Name',
        'secondary_field': None,
        'secondary_label': None,
    },
    'regimen': {
        'title': 'Chemotherapy Regimens',
        'table_name': 'sbtblChemoRegimen',
        'app': 'systemic',
        'model_name': 'ChemoRegimen',
        'pk': 'regimen_id',
        'name_field': 'regimen_code',
        'name_label': 'Regimen Code (e.g. Cisplatin Weekly, TP)',
        'secondary_field': 'regimen_description',
        'secondary_label': 'Description (e.g. Cisplatin 40mg/m2)',
    },
    'agent': {
        'title': 'Chemotherapy Agents',
        'table_name': 'sbtblChemoAgent',
        'app': 'systemic',
        'model_name': 'ChemoAgent',
        'pk': 'agent_id',
        'name_field': 'agent_name',
        'name_label': 'Chemotherapy Drug Name (e.g. Cisplatin, Carboplatin)',
        'secondary_field': 'agent_class',
        'secondary_label': 'Drug Class (e.g. Platinum, Taxane)',
    },
    'staging_system': {
        'title': 'Staging Systems (FIGO / TNM)',
        'table_name': 'sbtblStagingSystem',
        'app': 'clinical',
        'model_name': 'StagingSystem',
        'pk': 'staging_system_id',
        'name_field': 'system_name',
        'name_label': 'Staging System Name (e.g. FIGO 2018, AJCC TNM 8th Ed)',
        'secondary_field': 'system_version',
        'secondary_label': 'Version / Edition (e.g. 2018, 8th Edition)',
    },
    'anaesthesia': {
        'title': 'Anaesthesia Types',
        'table_name': 'sbtblAnaesthesiaType',
        'app': 'radiotherapy',
        'model_name': 'AnaesthesiaType',
        'pk': 'anaesthesia_id',
        'name_field': 'anaesthesia_name',
        'name_label': 'Anaesthesia Name (e.g. Spinal, GA, Sedation)',
        'secondary_field': None,
        'secondary_label': None,
    },
    'grade': {
        'title': 'Tumour Grades',
        'table_name': 'sbtblGrade',
        'app': 'clinical',
        'model_name': 'Grade',
        'pk': 'grade_id',
        'name_field': 'grade_name',
        'name_label': 'Tumour Grade (e.g. G1, G2, G3)',
        'secondary_field': None,
        'secondary_label': None,
    },
}

def get_lookup_model(category):
    cfg = LOOKUP_CONFIG.get(category)
    if not cfg:
        return None, None
    from django.apps import apps
    model = apps.get_model(cfg['app'], cfg['model_name'])
    return model, cfg

@login_required
def lookup_manager_view(request, category='source'):
    """Replicates Access Dropdown Configuration & Lookup Tables Manager."""
    if not is_admin_user(request.user):
        messages.error(request, "Access denied. Dropdown management requires administrator privileges.")
        return redirect('dashboard')

    if category not in LOOKUP_CONFIG:
        category = 'source'

    from core.lookup_defaults import get_default_lookup_id
    model, cfg = get_lookup_model(category)
    default_id = get_default_lookup_id(category)

    raw_items = model.objects.all().order_by('display_order', cfg['name_field'])
    items = []
    default_item = None
    for it in raw_items:
        is_def = (str(it.pk) == str(default_id)) if default_id is not None else False
        item_dict = {
            'pk': it.pk,
            'display_order': getattr(it, 'display_order', 1),
            'name': getattr(it, cfg['name_field'], str(it)),
            'secondary': getattr(it, cfg['secondary_field'], '') if cfg['secondary_field'] else '',
            'is_active': getattr(it, 'is_active', True),
            'is_default': is_def,
        }
        items.append(item_dict)
        if is_def:
            default_item = item_dict

    return render(request, 'core/lookup_manager.html', {
        'category': category,
        'cfg': cfg,
        'items': items,
        'default_id': default_id,
        'default_item': default_item,
        'lookup_categories': LOOKUP_CONFIG,
    })

@login_required
def lookup_save_view(request, category, item_id=None):
    """Add or edit an option in the selected lookup table."""
    if not is_admin_user(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    from django.db.models import Max
    from core.models import AuditLog
    from core.lookup_defaults import get_default_lookup_id, set_default_lookup_id, clear_default_lookup_id

    model, cfg = get_lookup_model(category)
    if not model:
        return redirect('lookup_manager', category='source')

    pk_field = cfg['pk']
    name_field = cfg['name_field']
    sec_field = cfg['secondary_field']

    if request.method == 'POST':
        if not item_id:
            raw_id = request.POST.get('item_id')
            if raw_id:
                try:
                    item_id = int(raw_id)
                except (ValueError, TypeError):
                    item_id = None

        item = get_object_or_404(model, **{pk_field: item_id}) if item_id else None
        name_val = request.POST.get('name_value', '').strip()
        sec_val = request.POST.get('secondary_value', '').strip() if sec_field else None
        order_val = int(request.POST.get('display_order') or 1)
        active_val = bool(request.POST.get('is_active', True))
        is_default_checked = bool(request.POST.get('is_default'))

        if not name_val:
            messages.error(request, "Name cannot be empty.")
            return redirect('lookup_manager', category=category)

        if not item:
            # Auto-increment integer primary key
            max_id = model.objects.aggregate(m=Max(pk_field))['m'] or 0
            new_pk = max_id + 1

            create_kwargs = {
                pk_field: new_pk,
                name_field: name_val,
                'display_order': order_val,
                'is_active': active_val,
            }
            if sec_field and sec_val:
                create_kwargs[sec_field] = sec_val

            item = model.objects.create(**create_kwargs)

            AuditLog.objects.create(
                username=request.user.username,
                full_name=request.user.first_name,
                action="INSERT",
                table_affected=cfg['table_name'],
                record_ref=f"ID:{new_pk}",
                notes=f"Added dropdown option '{name_val}' to {cfg['title']}"
            )

            if is_default_checked:
                set_default_lookup_id(category, new_pk, user=request.user)

            messages.success(request, f"Option '{name_val}' added to {cfg['title']}.")
        else:
            setattr(item, name_field, name_val)
            if sec_field:
                setattr(item, sec_field, sec_val)
            item.display_order = order_val
            item.is_active = active_val
            item.save()

            AuditLog.objects.create(
                username=request.user.username,
                full_name=request.user.first_name,
                action="UPDATE",
                table_affected=cfg['table_name'],
                record_ref=f"ID:{getattr(item, pk_field)}",
                notes=f"Updated dropdown option '{name_val}' in {cfg['title']}"
            )

            cur_def = get_default_lookup_id(category)
            if is_default_checked:
                set_default_lookup_id(category, getattr(item, pk_field), user=request.user)
            elif cur_def is not None and str(cur_def) == str(getattr(item, pk_field)):
                clear_default_lookup_id(category, user=request.user)

            messages.success(request, f"Option '{name_val}' updated successfully.")

    return redirect('lookup_manager', category=category)

@login_required
def lookup_toggle_active_view(request, category, item_id):
    """Toggles active/inactive status for a dropdown option."""
    if not is_admin_user(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    from core.models import AuditLog

    model, cfg = get_lookup_model(category)
    if not model:
        return redirect('lookup_manager', category='source')

    pk_field = cfg['pk']
    item = get_object_or_404(model, **{pk_field: item_id})
    item.is_active = not item.is_active
    item.save()

    AuditLog.objects.create(
        username=request.user.username,
        full_name=request.user.first_name,
        action="UPDATE",
        table_affected=cfg['table_name'],
        record_ref=f"ID:{item_id}",
        notes=f"Toggled option '{getattr(item, cfg['name_field'])}' active status to {item.is_active}"
    )
    messages.success(request, f"Option status set to {'Active' if item.is_active else 'Inactive'}.")
    return redirect('lookup_manager', category=category)

@login_required
def lookup_set_default_view(request, category, item_id):
    """Sets the designated option as default for the given lookup table."""
    if not is_admin_user(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    from core.lookup_defaults import set_default_lookup_id
    model, cfg = get_lookup_model(category)
    if not model:
        return redirect('lookup_manager', category='source')

    pk_field = cfg['pk']
    item = get_object_or_404(model, **{pk_field: item_id})
    set_default_lookup_id(category, getattr(item, pk_field), user=request.user)
    name_val = getattr(item, cfg['name_field'], str(item))
    messages.success(request, f"Option '{name_val}' is now set as the default value for {cfg['title']}.")
    return redirect('lookup_manager', category=category)

@login_required
def lookup_clear_default_view(request, category):
    """Clears the default option for the given lookup table."""
    if not is_admin_user(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    from core.lookup_defaults import clear_default_lookup_id
    _, cfg = get_lookup_model(category)
    title = cfg['title'] if cfg else category
    clear_default_lookup_id(category, user=request.user)
    messages.info(request, f"Default option cleared for {title}.")
    return redirect('lookup_manager', category=category)

@login_required
def lookup_quick_default_view(request, category):
    """Selects the default option via the top quick-select dropdown."""
    if not is_admin_user(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    if request.method == 'POST':
        from core.lookup_defaults import set_default_lookup_id, clear_default_lookup_id
        item_id = request.POST.get('default_item_id')
        model, cfg = get_lookup_model(category)
        if item_id:
            pk_field = cfg['pk']
            item = get_object_or_404(model, **{pk_field: item_id})
            set_default_lookup_id(category, getattr(item, pk_field), user=request.user)
            name_val = getattr(item, cfg['name_field'], str(item))
            messages.success(request, f"Default value for {cfg['title']} set to '{name_val}'.")
        else:
            clear_default_lookup_id(category, user=request.user)
            messages.info(request, f"Default option cleared for {cfg['title']}.")

    return redirect('lookup_manager', category=category)


# --- Clinical Treatment Routing & Senior Consultant Sign-Off ---

@login_required
def nact_router_view(request, mr_no):
    """Direct route from Dashboard NACT cell to patient's NACT course."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = patient.nact_courses.filter(soft_deleted=False).first()
    if course:
        return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)
    return redirect('nact_add', mr_no=patient.mr_no)


@login_required
def ebrt_router_view(request, mr_no):
    """Direct route from Dashboard EBRT cell to patient's EBRT course."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = patient.ebrt_courses.filter(soft_deleted=False).first()
    if course:
        return redirect('ebrt_edit', mr_no=patient.mr_no, course_id=course.ebrt_course_id)
    return redirect('ebrt_add', mr_no=patient.mr_no)


@login_required
def adjuvant_router_view(request, mr_no):
    """Direct route from Dashboard Adj Chemo cell to patient's Adjuvant Chemotherapy course."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = patient.adjuvant_courses.filter(soft_deleted=False).first()
    if course:
        return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)
    return redirect('adjuvant_add', mr_no=patient.mr_no)


@login_required
def brachy_router_view(request, mr_no):
    """Direct route to patient's Brachytherapy course."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = patient.brachy_courses.filter(soft_deleted=False).first()
    if course:
        return redirect('brachy_edit', mr_no=patient.mr_no, course_id=course.brachy_course_id)
    return redirect('brachy_add', mr_no=patient.mr_no)


@login_required
def treatment_approve_toggle(request, course_type, course_id):
    """
    Formal Senior Consultant / Administrator Sign-off and Locking Workflow.
    Independent from clinical completion status. Requires credential verification and creates audit log.
    """
    if request.method != 'POST':
        return HttpResponseBadRequest("Invalid request method.")

    password = request.POST.get('password', '').strip()
    action_type = request.POST.get('action_type', 'approve')

    # Password check
    if not request.user.check_password(password):
        messages.error(request, "Authentication failed: Incorrect password. Action aborted.")
        return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

    # Check permission
    role = getattr(request.user, 'profile', None) and request.user.profile.role
    is_authorized = request.user.is_superuser or request.user.is_staff or (
        role and ((action_type == 'approve' and role.cap_approve) or (action_type == 'unapprove' and role.cap_unlock_approved))
    )

    if not is_authorized:
        messages.error(request, f"Permission Denied: Your account role does not have authority to {action_type} this clinical record.")
        return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

    course = None
    form_name = ""
    mr_no = ""
    if course_type == 'nact':
        course = get_object_or_404(NACTCourse, nact_course_id=course_id)
        form_name = "frmNACT"
        mr_no = course.patient.mr_no
    elif course_type == 'ebrt':
        course = get_object_or_404(EBRTCourse, ebrt_course_id=course_id)
        form_name = "frmEBRTCourse"
        mr_no = course.patient.mr_no
    elif course_type == 'adjuvant':
        course = get_object_or_404(AdjuvantChemoCourse, adjuvant_course_id=course_id)
        form_name = "frmAdjuvantCourse"
        mr_no = course.patient.mr_no
    elif course_type == 'brachy':
        course = get_object_or_404(BrachyCourse, brachy_course_id=course_id)
        form_name = "frmBrachyCourse"
        mr_no = course.patient.mr_no
    else:
        messages.error(request, "Unknown treatment course type.")
        return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

    role_name = role.role_name if role else ("Administrator" if request.user.is_superuser else "Senior Consultant")

    if action_type == 'approve':
        if course_type == 'brachy':
            from radiotherapy.validators import validate_applicator_measurements
            for sess in course.sessions.all():
                s_meas = {
                    'tandem_length_cm': sess.tandem_length_cm,
                    'ovoid_diameter_mm': sess.ovoid_diameter_mm,
                    'ovoid_length_mm': sess.ovoid_length_mm,
                    'ring_diameter_mm': sess.ring_diameter_mm,
                    'needle_count': sess.needle_count,
                }
                errs = validate_applicator_measurements(sess.applicator, s_meas, is_completing_or_approving=True)
                if errs:
                    err_msg = "; ".join(errs.values())
                    messages.error(
                        request,
                        f"Approval Rejected: Brachy Application #{sess.session_number} ({sess.applicator.name}) cannot be approved: {err_msg}"
                    )
                    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

        course.is_approved = True
        course.approval_locked = True
        course.approved_by = request.user.username
        course.approved_on = timezone.now()
        course.save()

        if course_type == 'brachy':
            for sess in course.sessions.all():
                sess.is_approved = True
                sess.approval_locked = True
                sess.approved_by = request.user.username
                sess.approved_on = timezone.now()
                sess.approved_rules = sess.get_rules_snapshot()
                sess.save()

        ApprovalAudit.objects.create(
            form_name=form_name,
            record_key=str(course_id),
            mr_no=mr_no,
            approval_action='Approved',
            approver_username=request.user.username,
            approver_full_name=request.user.get_full_name() or request.user.username,
            approver_role=role_name,
            action_on=timezone.now(),
            requested_by=request.user.username
        )
        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.get_full_name(),
            action="APPROVE",
            table_affected=form_name,
            record_ref=f"{mr_no}-{course_type.upper()}#{course_id}",
            notes=f"Formally approved & locked by {request.user.username} ({role_name})"
        )
        messages.success(request, f"Treatment course for {mr_no} formally approved and locked against editing.")
    else:
        course.is_approved = False
        course.approval_locked = False
        course.save()

        if course_type == 'brachy':
            for sess in course.sessions.all():
                sess.is_approved = False
                sess.approval_locked = False
                sess.save()

        ApprovalAudit.objects.create(
            form_name=form_name,
            record_key=str(course_id),
            mr_no=mr_no,
            approval_action='Unlocked',
            approver_username=request.user.username,
            approver_full_name=request.user.get_full_name() or request.user.username,
            approver_role=role_name,
            action_on=timezone.now(),
            requested_by=request.user.username
        )
        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.get_full_name(),
            action="UNLOCK",
            table_affected=form_name,
            record_ref=f"{mr_no}-{course_type.upper()}#{course_id}",
            notes=f"Unlocked by {request.user.username} ({role_name})"
        )
        messages.warning(request, f"Treatment course for {mr_no} unlocked. Routine modifications are now enabled.")

    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

