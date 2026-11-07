from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, date

from patients.models import Patient
from core.models import AuditLog
from radiotherapy.models import EBRTCourse, BrachyCourse
from systemic.models import (
    ConcurrentChemoCourse, ConcurrentChemoCycle, ConcurrentChemoDrug,
    NACTCourse, NACTCycle, NACTDrug,
    AdjuvantChemoCourse, AdjuvantChemoCycle, AdjuvantChemoDrug,
    ChemoAgent, ChemoRegimen, ChemoRoute, DoseUnit, NACTStatus, ResponseStatus
)

def parse_date_str(val):
    """Safely parses string to date object."""
    if not val:
        return None
    if isinstance(val, date):
        return val
    try:
        return datetime.strptime(str(val).strip(), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def resequence_nact_cycles(course):
    """
    Re-sequences NACT cycles strictly in chronological order by cycle_date.
    Updates cycle_number so Cycle #1 is the earliest date.
    """
    if not course or not course.nact_course_id:
        return
    cycles = list(course.cycles.all().order_by('cycle_date', 'nact_cycle_id'))
    for idx, cyc in enumerate(cycles, start=1):
        if cyc.cycle_number != idx:
            cyc.cycle_number = idx
            cyc.save(update_fields=['cycle_number'])


def resequence_adjuvant_cycles(course):
    """
    Re-sequences Adjuvant cycles strictly in chronological order by cycle_date.
    Updates cycle_number so Cycle #1 is the earliest date.
    """
    if not course or not course.adjuvant_course_id:
        return
    cycles = list(course.cycles.all().order_by('cycle_date', 'adjuvant_cycle_id'))
    for idx, cyc in enumerate(cycles, start=1):
        if cyc.cycle_number != idx:
            cyc.cycle_number = idx
            cyc.save(update_fields=['cycle_number'])


def resequence_concurrent_cycles(course):
    """
    Re-sequences Concurrent Chemotherapy cycles strictly in chronological order by cycle_date (oldest first).
    Updates cycle_number so Cycle #1 is the earliest date.
    """
    if not course or not course.conc_chemo_course_id:
        return
    cycles = list(course.cycles.all().order_by('cycle_date', 'conc_chemo_cycle_id'))
    for idx, cyc in enumerate(cycles, start=1):
        if cyc.cycle_number != idx:
            cyc.cycle_number = idx
            cyc.save(update_fields=['cycle_number'])


def validate_nact_cycle_date(course, cycle_date):
    """
    Validation Rules for NACT cycle date:
    1. Must fall between Course Start Date and Course End Date (if specified).
    2. Must strictly precede linked definitive treatment (EBRT / Brachy).
    """
    if not cycle_date:
        return False, "Cycle date is mandatory."

    if course.nact_start_date and cycle_date < course.nact_start_date:
        return False, f"Validation Failed: NACT cycle date ({cycle_date.strftime('%d-%b-%Y')}) cannot be earlier than Course Start Date ({course.nact_start_date.strftime('%d-%b-%Y')})."

    if course.nact_end_date and cycle_date > course.nact_end_date:
        return False, f"Validation Failed: NACT cycle date ({cycle_date.strftime('%d-%b-%Y')}) cannot be later than Course End Date ({course.nact_end_date.strftime('%d-%b-%Y')})."

    if course.linked_ebrt_course and course.linked_ebrt_course.ebrt_start_date:
        if cycle_date >= course.linked_ebrt_course.ebrt_start_date:
            return False, f"Validation Failed: NACT cycle date ({cycle_date.strftime('%d-%b-%Y')}) must precede linked EBRT start date ({course.linked_ebrt_course.ebrt_start_date.strftime('%d-%b-%Y')})."

    if course.linked_brachy_course and course.linked_brachy_course.brachy_start_date:
        if cycle_date >= course.linked_brachy_course.brachy_start_date:
            return False, f"Validation Failed: NACT cycle date ({cycle_date.strftime('%d-%b-%Y')}) must precede linked Brachytherapy start date ({course.linked_brachy_course.brachy_start_date.strftime('%d-%b-%Y')})."

    return True, ""


def validate_adjuvant_cycle_date(course, cycle_date):
    """
    Validation Rules for Adjuvant cycle date:
    1. Must fall between Course Start Date and Course End Date (if specified).
    2. Must strictly follow prior treatment completion (EBRT / Brachy).
    """
    if not cycle_date:
        return False, "Cycle date is mandatory."

    if course.adjuvant_start_date and cycle_date < course.adjuvant_start_date:
        return False, f"Validation Failed: Adjuvant cycle date ({cycle_date.strftime('%d-%b-%Y')}) cannot be earlier than Course Start Date ({course.adjuvant_start_date.strftime('%d-%b-%Y')})."

    if course.adjuvant_end_date and cycle_date > course.adjuvant_end_date:
        return False, f"Validation Failed: Adjuvant cycle date ({cycle_date.strftime('%d-%b-%Y')}) cannot be later than Course End Date ({course.adjuvant_end_date.strftime('%d-%b-%Y')})."

    # Brachytherapy link boundary
    if course.linked_brachy_course:
        br_end = course.linked_brachy_course.brachy_end_date
        if not br_end:
            last_sess = course.linked_brachy_course.sessions.order_by('-session_date').first()
            if last_sess:
                br_end = last_sess.session_date
        if br_end and cycle_date <= br_end:
            return False, f"Validation Failed: Adjuvant cycle date ({cycle_date.strftime('%d-%b-%Y')}) must follow prior Brachytherapy completion date ({br_end.strftime('%d-%b-%Y')})."

    # EBRT link boundary
    if course.linked_ebrt_course:
        ebrt_end = course.linked_ebrt_course.ebrt_end_date
        if ebrt_end and cycle_date <= ebrt_end:
            return False, f"Validation Failed: Adjuvant cycle date ({cycle_date.strftime('%d-%b-%Y')}) must follow prior EBRT completion date ({ebrt_end.strftime('%d-%b-%Y')})."

    return True, ""


@login_required
def systemic_hub_view(request, mr_no):
    """Central Systemic Chemotherapy Hub replicating frmSystemic with Concurrent, NACT and Adjuvant tabs."""
    patient = get_object_or_404(Patient, mr_no=mr_no)

    concurrent_courses = patient.concurrent_chemo_courses.filter(soft_deleted=False).prefetch_related('cycles__drugs__chemo_agent')
    nact_courses = patient.nact_courses.filter(soft_deleted=False).prefetch_related('cycles__drugs__chemo_agent')
    adjuvant_courses = patient.adjuvant_courses.all().prefetch_related('cycles__drugs__chemo_agent')

    active_tab = request.GET.get('tab', 'nact')

    return render(request, 'systemic/systemic_hub.html', {
        'patient': patient,
        'concurrent_courses': concurrent_courses,
        'nact_courses': nact_courses,
        'adjuvant_courses': adjuvant_courses,
        'active_tab': active_tab,
    })


# ==============================================================================
# NEOADJUVANT CHEMOTHERAPY (NACT) WORKFLOW
# ==============================================================================

@login_required
def nact_form_view(request, mr_no, course_id=None):
    """
    NACT Course Management replicating frmNACT.
    Hierarchy: tblNACTCourse -> tblNACTCycles -> tblNACTDrugs.
    Includes forward linking to EBRT/Brachy, cycle count validations, inline drug grid.
    """
    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(NACTCourse, nact_course_id=course_id, patient=patient) if course_id else None

    regimens = ChemoRegimen.objects.filter(is_active=True)
    responses = ResponseStatus.objects.filter(is_active=True)
    statuses = NACTStatus.objects.filter(is_active=True)
    ebrt_courses = patient.ebrt_courses.filter(soft_deleted=False)
    brachy_courses = patient.brachy_courses.filter(soft_deleted=False)
    agents = ChemoAgent.objects.filter(is_active=True)
    dose_units = DoseUnit.objects.filter(is_active=True)
    routes = ChemoRoute.objects.filter(is_active=True)

    if request.method == 'POST':
        if course and course.approval_locked:
            messages.error(request, "This record is formally approved and locked against routine modifications.")
            return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)

        if not course:
            course = NACTCourse(patient=patient, entered_by=request.user.username)

        nact_received = request.POST.get('nact_received') == '1'
        course.nact_received = nact_received

        if nact_received:
            course.chemo_regimen_id = request.POST.get('chemo_regimen_id') or None
            course.planned_cycles = int(request.POST.get('planned_cycles') or 3)
            rc_val = request.POST.get('received_cycles')
            if rc_val and rc_val.strip():
                course.received_cycles = int(rc_val)
            else:
                course.received_cycles = course.planned_cycles or 3
            course.cycle_frequency_days = int(request.POST.get('cycle_frequency_days') or 21)
            course.nact_start_date = parse_date_str(request.POST.get('nact_start_date'))
            course.nact_end_date = parse_date_str(request.POST.get('nact_end_date'))
            course.response_to_nact_id = request.POST.get('response_id') or None
            course.nact_status_id = request.POST.get('nact_status_id') or None
            course.linked_ebrt_course_id = request.POST.get('linked_ebrt_course_id') or None
            course.linked_brachy_course_id = request.POST.get('linked_brachy_course_id') or None
            course.post_nact_assessment_done = bool(request.POST.get('post_nact_assessment_done'))
            course.post_nact_mri_done = bool(request.POST.get('post_nact_mri_done'))

            # Validate date order for course start and end
            if course.nact_start_date and course.nact_end_date and course.nact_end_date < course.nact_start_date:
                messages.error(request, "Validation Failed: NACT End Date cannot precede Start Date.")
                return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id) if course.nact_course_id else redirect('nact_add', mr_no=patient.mr_no)

            # Validate all existing cycles against newly selected definitive treatment links
            if course.nact_course_id:
                for cyc in course.cycles.all():
                    is_valid, err_msg = validate_nact_cycle_date(course, cyc.cycle_date)
                    if not is_valid:
                        messages.error(request, err_msg)
                        return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)
        else:
            course.chemo_regimen = None
            course.received_cycles = 0
            course.linked_ebrt_course = None
            course.linked_brachy_course = None

        course.notes = request.POST.get('notes', '')
        course.save()

        # Initial Cycle / Drug quick entry (if filled and course currently has no cycles)
        if nact_received and not course.cycles.exists():
            quick_cycle_date = parse_date_str(request.POST.get('quick_cycle_date'))
            quick_agent_id = request.POST.get('quick_chemo_agent_id')
            if quick_cycle_date or quick_agent_id:
                c_date = quick_cycle_date or course.nact_start_date or date.today()
                is_valid, err_msg = validate_nact_cycle_date(course, c_date)
                if not is_valid:
                    messages.warning(request, f"Course parameters saved, but initial cycle date is invalid: {err_msg}")
                else:
                    cycle = NACTCycle.objects.create(
                        course=course,
                        cycle_number=1,
                        cycle_date=c_date,
                        cycle_status=request.POST.get('quick_cycle_status') or 'Administered',
                        pre_cycle_notes=request.POST.get('quick_pre_cycle_notes', ''),
                        cycle_toxicity=request.POST.get('quick_cycle_toxicity', '')
                    )
                    if not course.nact_start_date:
                        course.nact_start_date = c_date
                    if quick_agent_id:
                        dose_val = float(request.POST.get('quick_dose')) if request.POST.get('quick_dose') else None
                        unit_val = int(request.POST.get('quick_dose_unit_id')) if request.POST.get('quick_dose_unit_id') else None
                        route_val = int(request.POST.get('quick_chemo_route_id')) if request.POST.get('quick_chemo_route_id') else None
                        days_val = int(request.POST.get('quick_no_of_days') or 1)
                        day_admin_val = int(request.POST.get('quick_day_of_administration') or 1)
                        is_admin = request.POST.get('quick_administered') != '0'
                        NACTDrug.objects.create(
                            cycle=cycle,
                            chemo_agent_id=int(quick_agent_id),
                            dose=dose_val,
                            dose_unit_id=unit_val,
                            chemo_route_id=route_val,
                            no_of_days=days_val,
                            day_of_administration=day_admin_val,
                            administered=is_admin
                        )
                    if course.received_cycles < 1:
                        course.received_cycles = max(1, course.planned_cycles)
                    course.save()

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="UPDATE" if course_id else "INSERT",
            table_affected="tblNACTCourse",
            record_ref=f"{patient.mr_no}-NACT#{course.nact_course_id}",
            notes=f"Saved NACT course ({'Given' if course.nact_received else 'Not Given'})"
        )

        messages.success(request, f"NACT record for {patient.pt_name} saved.")
        if 'save_next' in request.POST:
            return redirect('radiotherapy_hub', mr_no=patient.mr_no)
        return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)

    if course:
        resequence_nact_cycles(course)
    cycles = course.cycles.all().order_by('cycle_date', 'nact_cycle_id').prefetch_related('drugs__chemo_agent', 'drugs__dose_unit', 'drugs__chemo_route') if course else []

    return render(request, 'systemic/nact_form.html', {
        'patient': patient,
        'course': course,
        'regimens': regimens,
        'responses': responses,
        'statuses': statuses,
        'ebrt_courses': ebrt_courses,
        'brachy_courses': brachy_courses,
        'cycles': cycles,
        'agents': agents,
        'dose_units': dose_units,
        'routes': routes,
    })


@login_required
def nact_cycle_add_view(request, mr_no, course_id):
    """
    Adds a new chemotherapy cycle under NACT course.
    Enforces Validation: Cycle count exceeds cycles given -> Warn and prevent the extra cycle.
    Enforces Validation: Cycle date follows linked definitive treatment -> Prevent save.
    """
    if request.method != 'POST':
        return redirect('nact_edit', mr_no=mr_no, course_id=course_id)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(NACTCourse, nact_course_id=course_id, patient=patient)

    if course.approval_locked:
        messages.error(request, "Record is locked against modifications.")
        return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)

    # Cycle limit check
    current_cycle_count = course.cycles.count()
    if current_cycle_count >= course.received_cycles:
        messages.error(
            request,
            f"Cannot add Cycle #{current_cycle_count + 1}. Total number of cycles given is set to {course.received_cycles}. "
            f"Please increase 'Total number of cycles given' in course parameters first before adding another cycle."
        )
        return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)

    cycle_date = parse_date_str(request.POST.get('cycle_date'))
    if not cycle_date:
        messages.error(request, "Cycle date is mandatory.")
        return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)

    # Date validation against linked definitive treatment
    is_valid, err_msg = validate_nact_cycle_date(course, cycle_date)
    if not is_valid:
        messages.error(request, err_msg)
        return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)

    cycle_num = current_cycle_count + 1
    cycle = NACTCycle.objects.create(
        course=course,
        cycle_number=cycle_num,
        cycle_date=cycle_date,
        cycle_status=request.POST.get('cycle_status', 'Administered'),
        pre_cycle_notes=request.POST.get('pre_cycle_notes', ''),
        cycle_toxicity=request.POST.get('cycle_toxicity', '')
    )

    chemo_agent_id = request.POST.get('chemo_agent_id')
    if chemo_agent_id:
        dose_val = float(request.POST.get('dose')) if request.POST.get('dose') else None
        unit_val = int(request.POST.get('dose_unit_id')) if request.POST.get('dose_unit_id') else None
        route_val = int(request.POST.get('chemo_route_id')) if request.POST.get('chemo_route_id') else None
        days_val = int(request.POST.get('no_of_days') or 1)
        day_admin_val = int(request.POST.get('day_of_administration') or 1)
        NACTDrug.objects.create(
            cycle=cycle,
            chemo_agent_id=int(chemo_agent_id),
            dose=dose_val,
            dose_unit_id=unit_val,
            chemo_route_id=route_val,
            no_of_days=days_val,
            day_of_administration=day_admin_val,
            administered=True
        )

    resequence_nact_cycles(course)
    messages.success(request, f"Cycle added successfully (auto-arranged in chronological order).")
    return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)


@login_required
def nact_cycle_edit_view(request, mr_no, course_id, cycle_id):
    """
    Updates an existing chemotherapy cycle under NACT course.
    Validates cycle date against linked definitive treatment.
    """
    if request.method != 'POST':
        return redirect('nact_edit', mr_no=mr_no, course_id=course_id)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(NACTCourse, nact_course_id=course_id, patient=patient)
    cycle = get_object_or_404(NACTCycle, nact_cycle_id=cycle_id, course=course)

    if course.approval_locked:
        messages.error(request, "Record is locked against modifications.")
        return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)

    cycle_date = parse_date_str(request.POST.get('cycle_date'))
    if not cycle_date:
        messages.error(request, "Cycle date is mandatory.")
        return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)

    # Date validation against linked definitive treatment & course start/end dates
    is_valid, err_msg = validate_nact_cycle_date(course, cycle_date)
    if not is_valid:
        messages.error(request, err_msg)
        return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)

    cycle.cycle_date = cycle_date
    cycle.cycle_status = request.POST.get('cycle_status') or cycle.cycle_status or 'Administered'
    if 'pre_cycle_notes' in request.POST:
        cycle.pre_cycle_notes = request.POST.get('pre_cycle_notes', '')
    if 'cycle_toxicity' in request.POST:
        cycle.cycle_toxicity = request.POST.get('cycle_toxicity', '')
    cycle.save()

    resequence_nact_cycles(course)
    messages.success(request, f"Cycle updated successfully (auto-arranged in chronological order).")
    return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)


@login_required
def nact_copy_previous_cycle_view(request, mr_no, course_id, cycle_id):
    """
    Replicates the previous cycle's drug regimen (agents, doses, units, days, route)
    into the current cycle.
    """
    if request.method != 'POST':
        return redirect('nact_edit', mr_no=mr_no, course_id=course_id)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(NACTCourse, nact_course_id=course_id, patient=patient)
    cycle = get_object_or_404(NACTCycle, nact_cycle_id=cycle_id, course=course)

    if course.approval_locked:
        messages.error(request, "Record is locked against modifications.")
        return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)

    prev_cycle = course.cycles.filter(cycle_number__lt=cycle.cycle_number).order_by('-cycle_number').first()
    if not prev_cycle or not prev_cycle.drugs.exists():
        messages.warning(request, "No previous cycle with drug administrations found to copy from.")
        return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)

    copied_count = 0
    for d in prev_cycle.drugs.all():
        NACTDrug.objects.create(
            cycle=cycle,
            chemo_agent=d.chemo_agent,
            dose=d.dose,
            dose_unit=d.dose_unit,
            no_of_days=d.no_of_days,
            day_of_administration=d.day_of_administration,
            chemo_route=d.chemo_route,
            administered=True
        )
        copied_count += 1

    messages.success(request, f"Copied {copied_count} drug administrations from Cycle #{prev_cycle.cycle_number} into Cycle #{cycle.cycle_number}.")
    return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)


@login_required
def nact_drug_save_view(request, mr_no, course_id, cycle_id, drug_id=None):
    """Adds or updates a drug row in a NACT cycle."""
    if request.method != 'POST':
        return redirect('nact_edit', mr_no=mr_no, course_id=course_id)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(NACTCourse, nact_course_id=course_id, patient=patient)
    cycle = get_object_or_404(NACTCycle, nact_cycle_id=cycle_id, course=course)

    if course.approval_locked:
        messages.error(request, "Record is locked.")
        return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)

    chemo_agent_id = request.POST.get('chemo_agent_id')
    if not chemo_agent_id:
        messages.error(request, "Please select a chemotherapy agent.")
        return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)

    dose_val = float(request.POST.get('dose')) if request.POST.get('dose') else None
    dose_unit_id = request.POST.get('dose_unit_id') or None
    no_of_days = int(request.POST.get('no_of_days') or 1)
    day_of_admin = int(request.POST.get('day_of_administration') or 1)
    chemo_route_id = request.POST.get('chemo_route_id') or None
    administered = request.POST.get('administered', '1') == '1'

    if drug_id:
        drug = get_object_or_404(NACTDrug, nact_drug_id=drug_id, cycle=cycle)
        drug.chemo_agent_id = chemo_agent_id
        drug.dose = dose_val
        drug.dose_unit_id = dose_unit_id
        drug.no_of_days = no_of_days
        drug.day_of_administration = day_of_admin
        drug.chemo_route_id = chemo_route_id
        drug.administered = administered
        drug.save()
        messages.success(request, f"Updated {drug.chemo_agent.agent_name} in Cycle #{cycle.cycle_number}.")
    else:
        NACTDrug.objects.create(
            cycle=cycle,
            chemo_agent_id=chemo_agent_id,
            dose=dose_val,
            dose_unit_id=dose_unit_id,
            no_of_days=no_of_days,
            day_of_administration=day_of_admin,
            chemo_route_id=chemo_route_id,
            administered=administered
        )
        messages.success(request, f"Drug added to Cycle #{cycle.cycle_number}.")

    return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)

nact_drug_add_view = nact_drug_save_view


@login_required
def nact_drug_delete_view(request, mr_no, course_id, cycle_id, drug_id):
    """Deletes a drug administration row from a NACT cycle."""
    if request.method != 'POST':
        return redirect('nact_edit', mr_no=mr_no, course_id=course_id)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(NACTCourse, nact_course_id=course_id, patient=patient)
    cycle = get_object_or_404(NACTCycle, nact_cycle_id=cycle_id, course=course)
    drug = get_object_or_404(NACTDrug, nact_drug_id=drug_id, cycle=cycle)

    if course.approval_locked:
        messages.error(request, "Record is locked.")
        return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)

    drug.delete()
    messages.success(request, "Drug administration removed.")
    return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)


@login_required
def nact_cycle_delete_view(request, mr_no, course_id, cycle_id):
    """Deletes a NACT cycle."""
    if request.method != 'POST':
        return redirect('nact_edit', mr_no=mr_no, course_id=course_id)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(NACTCourse, nact_course_id=course_id, patient=patient)
    cycle = get_object_or_404(NACTCycle, nact_cycle_id=cycle_id, course=course)

    if course.approval_locked:
        messages.error(request, "Record is locked.")
        return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)

    cycle.delete()
    resequence_nact_cycles(course)
    messages.success(request, f"Cycle deleted.")
    return redirect('nact_edit', mr_no=patient.mr_no, course_id=course.nact_course_id)


# ==============================================================================
# ADJUVANT CHEMOTHERAPY WORKFLOW
# ==============================================================================

@login_required
def adjuvant_form_view(request, mr_no, course_id=None):
    """
    Adjuvant Chemotherapy Course Management replicating frmAdjuvantCourse.
    Hierarchy: tblAdjuvantCourse -> tblAdjuvantCycles -> tblAdjuvantDrugs.
    Links backward to prior EBRT and/or Brachytherapy with completion date boundary validations.
    """
    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(AdjuvantChemoCourse, adjuvant_course_id=course_id, patient=patient) if course_id else None

    statuses = NACTStatus.objects.filter(is_active=True)
    ebrt_courses = patient.ebrt_courses.filter(soft_deleted=False)
    brachy_courses = patient.brachy_courses.filter(soft_deleted=False)
    agents = ChemoAgent.objects.filter(is_active=True)
    dose_units = DoseUnit.objects.filter(is_active=True)
    routes = ChemoRoute.objects.filter(is_active=True)

    if request.method == 'POST':
        if course and course.approval_locked:
            messages.error(request, "This record is formally approved and locked against routine modifications.")
            return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)

        if not course:
            course = AdjuvantChemoCourse(patient=patient, entered_by=request.user.username)

        adj_received = request.POST.get('adjuvant_received') == '1'
        course.adjuvant_received = adj_received

        if adj_received:
            course.planned_cycles = int(request.POST.get('planned_cycles') or 4)
            course.received_cycles = int(request.POST.get('received_cycles') or 0)
            course.adjuvant_start_date = parse_date_str(request.POST.get('adjuvant_start_date'))
            course.adjuvant_end_date = parse_date_str(request.POST.get('adjuvant_end_date'))
            course.chemo_status_id = request.POST.get('chemo_status_id') or None
            course.linked_ebrt_course_id = request.POST.get('linked_ebrt_course_id') or None
            course.linked_brachy_course_id = request.POST.get('linked_brachy_course_id') or None

            # Validate date order for course start and end
            if course.adjuvant_start_date and course.adjuvant_end_date and course.adjuvant_end_date < course.adjuvant_start_date:
                messages.error(request, "Validation Failed: Adjuvant End Date cannot precede Start Date.")
                return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id) if course.adjuvant_course_id else redirect('adjuvant_add', mr_no=patient.mr_no)

            # Validate all existing cycles against newly linked prior treatment boundaries & start/end dates
            if course.adjuvant_course_id:
                for cyc in course.cycles.all():
                    is_valid, err_msg = validate_adjuvant_cycle_date(course, cyc.cycle_date)
                    if not is_valid:
                        messages.error(request, err_msg)
                        return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)
        else:
            course.received_cycles = 0
            course.adjuvant_start_date = None
            course.adjuvant_end_date = None
            course.linked_ebrt_course = None
            course.linked_brachy_course = None

        course.notes = request.POST.get('notes', '')
        course.save()

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="UPDATE" if course_id else "INSERT",
            table_affected="tblAdjuvantCourse",
            record_ref=f"{patient.mr_no}-Adj#{course.adjuvant_course_id}",
            notes=f"Saved adjuvant chemotherapy course ({'Given' if course.adjuvant_received else 'Not Given'})"
        )

        messages.success(request, f"Adjuvant chemotherapy record for {patient.pt_name} saved.")
        if 'save_next' in request.POST:
            return redirect('followup_list', mr_no=patient.mr_no)
        return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)

    if course:
        resequence_adjuvant_cycles(course)
    cycles = course.cycles.all().order_by('cycle_date', 'adjuvant_cycle_id').prefetch_related('drugs__chemo_agent', 'drugs__dose_unit', 'drugs__chemo_route') if course else []

    return render(request, 'systemic/adjuvant_form.html', {
        'patient': patient,
        'course': course,
        'statuses': statuses,
        'ebrt_courses': ebrt_courses,
        'brachy_courses': brachy_courses,
        'cycles': cycles,
        'agents': agents,
        'dose_units': dose_units,
        'routes': routes,
    })


@login_required
def adjuvant_cycle_add_view(request, mr_no, course_id):
    """
    Adds a new cycle under Adjuvant Chemotherapy course.
    Enforces Validation: Cycle count exceeds cycles given -> Warn and prevent the extra cycle.
    Enforces Validation: Cycle date precedes prior treatment completion -> Prevent save.
    """
    if request.method != 'POST':
        return redirect('adjuvant_edit', mr_no=mr_no, course_id=course_id)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(AdjuvantChemoCourse, adjuvant_course_id=course_id, patient=patient)

    if course.approval_locked:
        messages.error(request, "Record is locked against modifications.")
        return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)

    # Cycle limit check
    current_cycle_count = course.cycles.count()
    if current_cycle_count >= course.received_cycles:
        messages.error(
            request,
            f"Cannot add Cycle #{current_cycle_count + 1}. Total number of cycles given is set to {course.received_cycles}. "
            f"Please increase 'Total number of cycles given' in course parameters first before adding another cycle."
        )
        return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)

    cycle_date = parse_date_str(request.POST.get('cycle_date'))
    if not cycle_date:
        messages.error(request, "Cycle date is mandatory.")
        return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)

    # Date validation against prior definitive treatment
    is_valid, err_msg = validate_adjuvant_cycle_date(course, cycle_date)
    if not is_valid:
        messages.error(request, err_msg)
        return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)

    cycle_num = current_cycle_count + 1
    cycle = AdjuvantChemoCycle.objects.create(
        course=course,
        cycle_number=cycle_num,
        cycle_date=cycle_date,
        cycle_status=request.POST.get('cycle_status', 'Administered'),
        pre_cycle_notes=request.POST.get('pre_cycle_notes', ''),
        cycle_toxicity=request.POST.get('cycle_toxicity', '')
    )

    resequence_adjuvant_cycles(course)
    messages.success(request, "Adjuvant cycle added successfully (auto-arranged in chronological order).")
    return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)


@login_required
def adjuvant_cycle_edit_view(request, mr_no, course_id, cycle_id):
    """
    Updates an existing chemotherapy cycle under Adjuvant Chemotherapy course.
    Validates cycle date against linked prior definitive treatment and course start/end dates.
    """
    if request.method != 'POST':
        return redirect('adjuvant_edit', mr_no=mr_no, course_id=course_id)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(AdjuvantChemoCourse, adjuvant_course_id=course_id, patient=patient)
    cycle = get_object_or_404(AdjuvantChemoCycle, adjuvant_cycle_id=cycle_id, course=course)

    if course.approval_locked:
        messages.error(request, "Record is locked against modifications.")
        return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)

    cycle_date = parse_date_str(request.POST.get('cycle_date'))
    if not cycle_date:
        messages.error(request, "Cycle date is mandatory.")
        return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)

    # Date validation against prior definitive treatment and course start/end dates
    is_valid, err_msg = validate_adjuvant_cycle_date(course, cycle_date)
    if not is_valid:
        messages.error(request, err_msg)
        return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)

    cycle.cycle_date = cycle_date
    cycle.cycle_status = request.POST.get('cycle_status') or cycle.cycle_status or 'Administered'
    if 'pre_cycle_notes' in request.POST:
        cycle.pre_cycle_notes = request.POST.get('pre_cycle_notes', '')
    if 'cycle_toxicity' in request.POST:
        cycle.cycle_toxicity = request.POST.get('cycle_toxicity', '')
    cycle.save()

    resequence_adjuvant_cycles(course)
    messages.success(request, "Adjuvant cycle updated successfully (auto-arranged in chronological order).")
    return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)


@login_required
def adjuvant_copy_previous_cycle_view(request, mr_no, course_id, cycle_id):
    """Copies previous cycle regimen into the selected cycle."""
    if request.method != 'POST':
        return redirect('adjuvant_edit', mr_no=mr_no, course_id=course_id)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(AdjuvantChemoCourse, adjuvant_course_id=course_id, patient=patient)
    cycle = get_object_or_404(AdjuvantChemoCycle, adjuvant_cycle_id=cycle_id, course=course)

    if course.approval_locked:
        messages.error(request, "Record is locked.")
        return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)

    prev_cycle = course.cycles.filter(cycle_number__lt=cycle.cycle_number).order_by('-cycle_number').first()
    if not prev_cycle or not prev_cycle.drugs.exists():
        messages.warning(request, "No previous cycle with drug administrations found to copy from.")
        return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)

    copied_count = 0
    for d in prev_cycle.drugs.all():
        AdjuvantChemoDrug.objects.create(
            cycle=cycle,
            chemo_agent=d.chemo_agent,
            dose=d.dose,
            dose_unit=d.dose_unit,
            no_of_days=d.no_of_days,
            day_of_administration=d.day_of_administration,
            chemo_route=d.chemo_route,
            administered=True
        )
        copied_count += 1

    messages.success(request, f"Copied {copied_count} drug administrations from Cycle #{prev_cycle.cycle_number} into Cycle #{cycle.cycle_number}.")
    return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)


@login_required
def adjuvant_drug_save_view(request, mr_no, course_id, cycle_id, drug_id=None):
    """Adds or updates a drug row in an Adjuvant Chemotherapy cycle."""
    if request.method != 'POST':
        return redirect('adjuvant_edit', mr_no=mr_no, course_id=course_id)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(AdjuvantChemoCourse, adjuvant_course_id=course_id, patient=patient)
    cycle = get_object_or_404(AdjuvantChemoCycle, adjuvant_cycle_id=cycle_id, course=course)

    if course.approval_locked:
        messages.error(request, "Record is locked.")
        return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)

    chemo_agent_id = request.POST.get('chemo_agent_id')
    if not chemo_agent_id:
        messages.error(request, "Please select a chemotherapy agent.")
        return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)

    dose_val = float(request.POST.get('dose')) if request.POST.get('dose') else None
    dose_unit_id = request.POST.get('dose_unit_id') or None
    no_of_days = int(request.POST.get('no_of_days') or 1)
    day_of_admin = int(request.POST.get('day_of_administration') or 1)
    chemo_route_id = request.POST.get('chemo_route_id') or None
    administered = request.POST.get('administered', '1') == '1'

    if drug_id:
        drug = get_object_or_404(AdjuvantChemoDrug, adjuvant_drug_id=drug_id, cycle=cycle)
        drug.chemo_agent_id = chemo_agent_id
        drug.dose = dose_val
        drug.dose_unit_id = dose_unit_id
        drug.no_of_days = no_of_days
        drug.day_of_administration = day_of_admin
        drug.chemo_route_id = chemo_route_id
        drug.administered = administered
        drug.save()
        messages.success(request, f"Updated {drug.chemo_agent.agent_name} in Adjuvant Cycle #{cycle.cycle_number}.")
    else:
        AdjuvantChemoDrug.objects.create(
            cycle=cycle,
            chemo_agent_id=chemo_agent_id,
            dose=dose_val,
            dose_unit_id=dose_unit_id,
            no_of_days=no_of_days,
            day_of_administration=day_of_admin,
            chemo_route_id=chemo_route_id,
            administered=administered
        )
        messages.success(request, f"Drug added to Adjuvant Cycle #{cycle.cycle_number}.")

    return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)

adjuvant_drug_add_view = adjuvant_drug_save_view


@login_required
def adjuvant_drug_delete_view(request, mr_no, course_id, cycle_id, drug_id):
    """Deletes a drug administration row from an Adjuvant cycle."""
    if request.method != 'POST':
        return redirect('adjuvant_edit', mr_no=mr_no, course_id=course_id)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(AdjuvantChemoCourse, adjuvant_course_id=course_id, patient=patient)
    cycle = get_object_or_404(AdjuvantChemoCycle, adjuvant_cycle_id=cycle_id, course=course)
    drug = get_object_or_404(AdjuvantChemoDrug, adjuvant_drug_id=drug_id, cycle=cycle)

    if course.approval_locked:
        messages.error(request, "Record is locked.")
        return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)

    drug.delete()
    messages.success(request, "Drug administration removed.")
    return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)


@login_required
def adjuvant_cycle_delete_view(request, mr_no, course_id, cycle_id):
    """Deletes an Adjuvant cycle."""
    if request.method != 'POST':
        return redirect('adjuvant_edit', mr_no=mr_no, course_id=course_id)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(AdjuvantChemoCourse, adjuvant_course_id=course_id, patient=patient)
    cycle = get_object_or_404(AdjuvantChemoCycle, adjuvant_cycle_id=cycle_id, course=course)

    if course.approval_locked:
        messages.error(request, "Record is locked.")
        return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)

    cycle.delete()
    resequence_adjuvant_cycles(course)
    messages.success(request, "Cycle deleted.")
    return redirect('adjuvant_edit', mr_no=patient.mr_no, course_id=course.adjuvant_course_id)


# ==============================================================================
# CONCURRENT CHEMOTHERAPY (STANDALONE SUBFORM HANDLERS)
# ==============================================================================

@login_required
def concurrent_form_view(request, mr_no, course_id=None):
    """Replicates frmConcurrentChemo."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(ConcurrentChemoCourse, conc_chemo_course_id=course_id, patient=patient) if course_id else None

    regimens = ChemoRegimen.objects.filter(is_active=True)
    ebrt_courses = patient.ebrt_courses.filter(soft_deleted=False)

    if request.method == 'POST':
        if not course:
            course = ConcurrentChemoCourse(patient=patient, entered_by=request.user.username)

        concurrent_received = request.POST.get('concurrent_received') == '1'
        course.concurrent_received = concurrent_received
        course.chemo_regimen_id = request.POST.get('chemo_regimen_id') or None
        course.planned_cycles = int(request.POST.get('planned_cycles') or 5)
        course.received_cycles = int(request.POST.get('received_cycles') or 0)
        course.cycle_frequency_days = int(request.POST.get('cycle_frequency_days') or 7)
        course.conc_chemo_start_date = parse_date_str(request.POST.get('conc_chemo_start_date'))
        course.conc_chemo_end_date = parse_date_str(request.POST.get('conc_chemo_end_date'))
        course.linked_ebrt_course_id = request.POST.get('linked_ebrt_course_id') or None
        course.completion_status = request.POST.get('completion_status', '')
        course.discontinuation_reason = request.POST.get('discontinuation_reason', '')
        course.notes = request.POST.get('notes', '')
        course.save()

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="UPDATE" if course_id else "INSERT",
            table_affected="tblConcurrentChemoCourse",
            record_ref=f"{patient.mr_no}-ConcChemo#{course.conc_chemo_course_id}",
            notes=f"Saved concurrent chemo: {course.chemo_regimen}"
        )

        messages.success(request, f"Concurrent chemotherapy course for {patient.pt_name} saved.")
        return redirect('systemic_hub', mr_no=patient.mr_no)

    if course:
        resequence_concurrent_cycles(course)
    cycles = course.cycles.all().order_by('cycle_date', 'conc_chemo_cycle_id').prefetch_related('drugs__chemo_agent', 'drugs__dose_unit') if course else []

    return render(request, 'systemic/concurrent_form.html', {
        'patient': patient,
        'course': course,
        'regimens': regimens,
        'ebrt_courses': ebrt_courses,
        'cycles': cycles,
    })


@login_required
def concurrent_cycle_form_view(request, mr_no, course_id, cycle_id=None):
    """Replicates frmConcurrentChemoCycles - Single chemotherapy cycle administration."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(ConcurrentChemoCourse, conc_chemo_course_id=course_id, patient=patient)
    cycle = get_object_or_404(ConcurrentChemoCycle, conc_chemo_cycle_id=cycle_id, course=course) if cycle_id else None

    agents = ChemoAgent.objects.filter(is_active=True)
    dose_units = DoseUnit.objects.filter(is_active=True)
    routes = ChemoRoute.objects.filter(is_active=True)
    drug = cycle.drugs.first() if cycle else None

    if request.method == 'POST':
        if not cycle:
            cycle = ConcurrentChemoCycle(course=course)

        cycle.cycle_number = int(request.POST.get('cycle_number') or 1)
        cycle.cycle_date = parse_date_str(request.POST.get('cycle_date')) or date.today()
        cycle.cycle_status = request.POST.get('cycle_status', 'Administered')
        cycle.cycle_toxicity = request.POST.get('cycle_toxicity', '')
        cycle.pre_cycle_notes = request.POST.get('pre_cycle_notes', '')
        cycle.post_cycle_notes = request.POST.get('post_cycle_notes', '')
        cycle.save()

        # Drug entry
        if not drug:
            drug = ConcurrentChemoDrug(cycle=cycle)

        drug.chemo_agent_id = request.POST.get('chemo_agent_id')
        drug.dose = float(request.POST.get('dose')) if request.POST.get('dose') else None
        drug.dose_unit_id = request.POST.get('dose_unit_id') or None
        drug.no_of_days = int(request.POST.get('no_of_days') or 1)
        drug.day_of_administration = int(request.POST.get('day_of_administration') or 1)
        drug.dose_mg = float(request.POST.get('dose_mg')) if request.POST.get('dose_mg') else None
        drug.dose_per_m2 = float(request.POST.get('dose_per_m2')) if request.POST.get('dose_per_m2') else None
        drug.bsa_m2 = float(request.POST.get('bsa_m2')) if request.POST.get('bsa_m2') else None
        drug.chemo_route_id = request.POST.get('chemo_route_id') or None
        drug.administered = request.POST.get('administered', '1') == '1'
        drug.save()

        # Update received count and re-sequence in chronological order
        course.received_cycles = course.cycles.count()
        course.save()
        resequence_concurrent_cycles(course)

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="UPDATE" if cycle_id else "INSERT",
            table_affected="tblConcurrentChemoCycles",
            record_ref=f"Cycle#{cycle.conc_chemo_cycle_id}",
            notes=f"Administered cycle #{cycle.cycle_number}"
        )

        messages.success(request, f"Concurrent chemo cycle #{cycle.cycle_number} saved.")
        return redirect('concurrent_edit', mr_no=patient.mr_no, course_id=course.conc_chemo_course_id)

    return render(request, 'systemic/concurrent_cycle_form.html', {
        'patient': patient,
        'course': course,
        'cycle': cycle,
        'drug': drug,
        'agents': agents,
        'dose_units': dose_units,
        'routes': routes,
    })
