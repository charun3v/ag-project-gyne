from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponseForbidden
from datetime import datetime, date
import json

from patients.models import Patient
from core.models import AuditLog
from core.views import is_admin_user
from radiotherapy.models import (
    EBRTCourse, EBRTIntent, EBRTTechnique, EBRTSite, TreatmentCentre, RTMachine,
    InterruptionReason, TreatmentCourseStatus, EBRTCourseSite, EBRTInterruption,
    BrachyCourse, BrachySourceType, BrachyDosing, BrachyApplicator, BrachyImageGuidance,
    AnaesthesiaType, BrachySessionStatus, BrachyFractionStatus, BrachySession, BrachyFraction,
    ApplicatorType, ApplicatorMeasurementDefinition, ApplicatorFieldRule
)
from radiotherapy.forms import BrachySessionForm
from radiotherapy.validators import validate_applicator_measurements
from systemic.models import (
    ConcurrentChemoCourse, ConcurrentChemoCycle, ConcurrentChemoDrug,
    ChemoRegimen, ChemoAgent, DoseUnit, ChemoRoute
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

@login_required
def radiotherapy_hub_view(request, mr_no):
    """Central Radiotherapy Hub replicating frmRadiotherapy with EBRT and Brachy subforms."""
    patient = get_object_or_404(Patient, mr_no=mr_no)

    ebrt_courses = patient.ebrt_courses.filter(soft_deleted=False).prefetch_related('sites__ebrt_site', 'interruptions')
    brachy_courses = patient.brachy_courses.filter(soft_deleted=False).prefetch_related(
        'sessions__fractions',
        'sessions__applicator',
        'sessions__image_guidance',
        'sessions__brachy_dosing',
        'sessions__brachy_source',
        'sessions__session_status',
        'treatment_centre',
        'linked_ebrt_course',
        'brachy_dosing',
        'brachy_source',
        'course_status'
    )

    # Compute Radiobiological EQD2 totals and Course Summary metrics
    eqd2_summary = []
    for br in brachy_courses:
        tumor_eqd2 = 0.0
        bladder_eqd2 = 0.0
        rectum_eqd2 = 0.0
        sigmoid_eqd2 = 0.0

        total_physical_dose = 0.0
        total_hrctv_d90 = 0.0
        total_rectum_2cc = 0.0
        total_bladder_2cc = 0.0
        total_sigmoid_2cc = 0.0
        total_fx_count = 0

        # Linked EBRT dose
        linked_ebrt = br.linked_ebrt_course or ebrt_courses.first()
        if linked_ebrt and linked_ebrt.total_dose_gy and linked_ebrt.total_fractions:
            ebrt_dose = linked_ebrt.total_dose_gy
            ebrt_fx = linked_ebrt.total_fractions
            tumor_eqd2 += BrachyFraction.calculate_eqd2(ebrt_dose, ebrt_fx, br.alpha_beta_tumor or 10.0)
            bladder_eqd2 += BrachyFraction.calculate_eqd2(ebrt_dose, ebrt_fx, br.alpha_beta_bladder or 3.0)
            rectum_eqd2 += BrachyFraction.calculate_eqd2(ebrt_dose, ebrt_fx, br.alpha_beta_rectum or 3.0)
            sigmoid_eqd2 += BrachyFraction.calculate_eqd2(ebrt_dose, ebrt_fx, br.alpha_beta_sigmoid or 3.0)

        # Add Brachy fractions & aggregate course totals
        for sess in br.sessions.all():
            for fx in sess.fractions.all():
                total_fx_count += 1
                if fx.dose_delivered_gy:
                    total_physical_dose += fx.dose_delivered_gy
                if fx.hrctv_d90_gy:
                    total_hrctv_d90 += fx.hrctv_d90_gy
                    tumor_eqd2 += BrachyFraction.calculate_eqd2(fx.hrctv_d90_gy, 1, br.alpha_beta_tumor or 10.0)
                elif fx.dose_delivered_gy:
                    tumor_eqd2 += BrachyFraction.calculate_eqd2(fx.dose_delivered_gy, 1, br.alpha_beta_tumor or 10.0)
                
                if fx.bladder_dose_2cc_gy:
                    total_bladder_2cc += fx.bladder_dose_2cc_gy
                    bladder_eqd2 += BrachyFraction.calculate_eqd2(fx.bladder_dose_2cc_gy, 1, br.alpha_beta_bladder or 3.0)
                if fx.rectum_dose_2cc_gy:
                    total_rectum_2cc += fx.rectum_dose_2cc_gy
                    rectum_eqd2 += BrachyFraction.calculate_eqd2(fx.rectum_dose_2cc_gy, 1, br.alpha_beta_rectum or 3.0)
                if fx.sigmoid_dose_2cc_gy:
                    total_sigmoid_2cc += fx.sigmoid_dose_2cc_gy
                    sigmoid_eqd2 += BrachyFraction.calculate_eqd2(fx.sigmoid_dose_2cc_gy, 1, br.alpha_beta_sigmoid or 3.0)

        # Keep total_fractions_delivered on model synchronized with actual fractions
        if br.total_fractions_delivered != total_fx_count:
            br.total_fractions_delivered = total_fx_count
            br.save(update_fields=['total_fractions_delivered'])

        # Keep total_fractions_planned synchronized so it never shows delivered > planned
        if not br.total_fractions_planned or br.total_fractions_planned < total_fx_count:
            br.total_fractions_planned = total_fx_count
            br.save(update_fields=['total_fractions_planned'])

        if not br.total_applications_planned:
            br.total_applications_planned = max(br.sessions.count(), 2)
            br.save(update_fields=['total_applications_planned'])

        # Attach computed summary attributes to course instance for template rendering
        br.summary_total_dose = round(total_physical_dose, 1)
        br.summary_total_hrctv_d90 = round(total_hrctv_d90, 1)
        br.summary_total_rectum = round(total_rectum_2cc, 1)
        br.summary_total_bladder = round(total_bladder_2cc, 1)
        br.summary_total_sigmoid = round(total_sigmoid_2cc, 1)
        br.summary_fx_count = total_fx_count
        br.summary_tumor_eqd2 = round(tumor_eqd2, 1)
        br.summary_bladder_eqd2 = round(bladder_eqd2, 1)
        br.summary_rectum_eqd2 = round(rectum_eqd2, 1)
        br.summary_sigmoid_eqd2 = round(sigmoid_eqd2, 1)

        eqd2_summary.append({
            'course': br,
            'tumor_eqd2': round(tumor_eqd2, 1),
            'bladder_eqd2': round(bladder_eqd2, 1),
            'rectum_eqd2': round(rectum_eqd2, 1),
            'sigmoid_eqd2': round(sigmoid_eqd2, 1),
        })

    return render(request, 'radiotherapy/radiotherapy_hub.html', {
        'patient': patient,
        'ebrt_courses': ebrt_courses,
        'brachy_courses': brachy_courses,
        'eqd2_summary': eqd2_summary,
    })


def validate_ebrt_chronology(simulation_date, contouring_date, plan_approval_date, ebrt_start_date, ebrt_end_date):
    """
    Enforces strict chronological sequence:
    Simulation Date <= Contouring Date <= Plan Approval Date <= RT Start Date <= RT End Date
    (Simulation date cannot be after contouring date - it can be on the same day or before).
    """
    if not simulation_date:
        return False, "Validation Failed: Simulation Date is mandatory for EBRT course."

    dates = [
        ("Simulation Date", simulation_date),
        ("Contouring Date", contouring_date),
        ("Plan Approval Date", plan_approval_date),
        ("RT Start Date", ebrt_start_date),
        ("RT End Date", ebrt_end_date),
    ]

    entered = [(name, d) for name, d in dates if d is not None]

    for i in range(len(entered) - 1):
        name_curr, d_curr = entered[i]
        name_next, d_next = entered[i + 1]
        if d_curr > d_next:
            return False, (
                f"Validation Failed: {name_curr} ({d_curr.strftime('%d-%b-%Y')}) cannot be after "
                f"{name_next} ({d_next.strftime('%d-%b-%Y')}). "
                f"Mandatory rule: Simulation Date <= Contouring Date <= Plan Approval Date <= RT Start Date <= RT End Date "
                f"(dates may be on the same day or sequential)."
            )

    return True, ""


@login_required
def ebrt_form_view(request, mr_no, course_id=None):
    """
    Replicates frmEBRTCourse - External beam RT course management.
    Includes planning date chronological validations, targets, gaps,
    and embedded concurrent chemotherapy workflow with completion constraints.
    """
    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(EBRTCourse, ebrt_course_id=course_id, patient=patient) if course_id else None

    intents = EBRTIntent.objects.filter(is_active=True)
    techniques = EBRTTechnique.objects.filter(is_active=True)
    centres = TreatmentCentre.objects.filter(is_active=True)
    machines = RTMachine.objects.filter(is_active=True)
    statuses = TreatmentCourseStatus.objects.filter(is_active=True)
    ebrt_sites = EBRTSite.objects.filter(is_active=True)
    interruption_reasons = InterruptionReason.objects.filter(is_active=True)

    chemo_regimens = ChemoRegimen.objects.filter(is_active=True)
    chemo_agents = ChemoAgent.objects.filter(is_active=True)
    dose_units = DoseUnit.objects.filter(is_active=True)
    chemo_routes = ChemoRoute.objects.filter(is_active=True)

    concurrent_course = course.concurrent_chemo_courses.first() if course else None

    if request.method == 'POST':
        if course and course.approval_locked:
            messages.error(request, "This record is formally approved and locked against routine modifications.")
            return redirect('ebrt_edit', mr_no=patient.mr_no, course_id=course.ebrt_course_id)

        # 1. Parse Planning and Treatment Dates
        simulation_date = parse_date_str(request.POST.get('simulation_date'))
        contouring_date = parse_date_str(request.POST.get('contouring_date'))
        plan_approval_date = parse_date_str(request.POST.get('plan_approval_date'))
        ebrt_start_date = parse_date_str(request.POST.get('ebrt_start_date'))
        ebrt_end_date = parse_date_str(request.POST.get('ebrt_end_date'))

        # Comprehensive Chronological Timeline Validation:
        # Simulation Date <= Contouring Date <= Plan Approval Date <= RT Start Date <= RT End Date
        is_valid_dates, date_err = validate_ebrt_chronology(
            simulation_date, contouring_date, plan_approval_date, ebrt_start_date, ebrt_end_date
        )
        if not is_valid_dates:
            messages.error(request, date_err)
            return redirect('ebrt_edit', mr_no=patient.mr_no, course_id=course.ebrt_course_id) if course else redirect('ebrt_add', mr_no=patient.mr_no)

        # Concurrent Chemotherapy parameters from POST
        concurrent_received = request.POST.get('concurrent_received') == '1'
        conc_regimen_id = request.POST.get('conc_chemo_regimen_id') or None
        conc_planned = int(request.POST.get('conc_planned_cycles') or 5)
        conc_received_raw = request.POST.get('conc_received_cycles')
        if conc_received_raw is not None and conc_received_raw != '':
            conc_received = int(conc_received_raw)
        elif concurrent_course and concurrent_course.received_cycles is not None:
            conc_received = concurrent_course.received_cycles
        else:
            conc_received = conc_planned

        # Validate existing concurrent chemotherapy dates within EBRT dates
        if concurrent_received and concurrent_course:
            for cyc in concurrent_course.cycles.all():
                if ebrt_start_date and cyc.cycle_date < ebrt_start_date:
                    messages.error(
                        request,
                        f"Validation Failed: Concurrent chemotherapy cycle #{cyc.cycle_number} date ({cyc.cycle_date}) "
                        f"lies outside the EBRT treatment dates (precedes RT start {ebrt_start_date})."
                    )
                    return redirect('ebrt_edit', mr_no=patient.mr_no, course_id=course.ebrt_course_id)
                if ebrt_end_date and cyc.cycle_date > ebrt_end_date:
                    messages.error(
                        request,
                        f"Validation Failed: Concurrent chemotherapy cycle #{cyc.cycle_number} date ({cyc.cycle_date}) "
                        f"lies outside the EBRT treatment dates (follows RT end {ebrt_end_date})."
                    )
                    return redirect('ebrt_edit', mr_no=patient.mr_no, course_id=course.ebrt_course_id)

        # Validation Matrix Rule: Declared concurrent cycles are incomplete -> Do not permit completion
        new_status_id = request.POST.get('course_status_id') or None
        status_obj = TreatmentCourseStatus.objects.filter(course_status_id=new_status_id).first() if new_status_id else None
        is_marking_completed = bool(request.POST.get('treatment_completed')) or (status_obj and 'complet' in status_obj.status_name.lower())

        if is_marking_completed and concurrent_received:
            # Check declared concurrent cycles completion
            total_declared = conc_planned
            completed_cycles = 0
            if concurrent_course:
                completed_cycles = concurrent_course.cycles.filter(cycle_status__in=['Administered', 'Completed']).count()

            if completed_cycles < total_declared:
                messages.error(
                    request,
                    f"Validation Failed: Cannot mark EBRT course as Completed because declared concurrent chemotherapy cycles "
                    f"({completed_cycles} completed of {total_declared} declared) are incomplete."
                )
                return redirect('ebrt_edit', mr_no=patient.mr_no, course_id=course.ebrt_course_id) if course else redirect('ebrt_add', mr_no=patient.mr_no)

        # Save EBRT Course
        if not course:
            course = EBRTCourse(patient=patient, entered_by=request.user.username)

        course.ebrt_intent_id = request.POST.get('ebrt_intent_id') or None
        course.ebrt_technique_id = request.POST.get('ebrt_technique_id') or None
        course.treatment_centre_id = request.POST.get('treatment_centre_id') or 1
        course.initial_rt_machine_id = request.POST.get('initial_rt_machine_id') or None
        course.course_status_id = new_status_id

        course.total_dose_gy = float(request.POST.get('total_dose_gy')) if request.POST.get('total_dose_gy') else None
        course.total_fractions = int(request.POST.get('total_fractions')) if request.POST.get('total_fractions') else None
        course.dose_per_fraction_gy = float(request.POST.get('dose_per_fraction_gy')) if request.POST.get('dose_per_fraction_gy') else None

        course.simulation_date = simulation_date
        course.contouring_date = contouring_date
        course.plan_approval_date = plan_approval_date
        course.ebrt_start_date = ebrt_start_date
        course.ebrt_end_date = ebrt_end_date

        course.treatment_interrupted = bool(request.POST.get('treatment_interrupted'))
        course.interruption_days = int(request.POST.get('interruption_days') or 0)
        course.long_gap_notes = request.POST.get('long_gap_notes', '')

        course.treatment_completed = bool(request.POST.get('treatment_completed'))
        course.completion_notes = request.POST.get('completion_notes', '')
        course.last_modified_by = request.user.username
        course.save()

        # Update EBRT Sites
        selected_sites = request.POST.getlist('ebrt_sites')
        if selected_sites:
            EBRTCourseSite.objects.filter(ebrt_course=course).delete()
            for s_id in selected_sites:
                EBRTCourseSite.objects.create(ebrt_course=course, ebrt_site_id=int(s_id))

        # Save Embedded Concurrent Chemotherapy Course
        if concurrent_received:
            if not concurrent_course:
                concurrent_course = ConcurrentChemoCourse.objects.create(
                    patient=patient,
                    linked_ebrt_course=course,
                    entered_by=request.user.username
                )
            concurrent_course.concurrent_received = True
            if conc_regimen_id:
                concurrent_course.chemo_regimen_id = conc_regimen_id
            concurrent_course.planned_cycles = conc_planned
            concurrent_course.received_cycles = conc_received
            concurrent_course.conc_chemo_start_date = ebrt_start_date
            concurrent_course.conc_chemo_end_date = ebrt_end_date
            concurrent_course.save()
        else:
            if concurrent_course:
                concurrent_course.concurrent_received = False
                concurrent_course.save()

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="UPDATE" if course_id else "INSERT",
            table_affected="tblEBRTCourse",
            record_ref=f"{patient.mr_no}-EBRT#{course.ebrt_course_id}",
            notes=f"Saved EBRT course: {course.total_dose_gy} Gy / {course.total_fractions}# (Concurrent: {'Yes' if concurrent_received else 'No'})"
        )

        if concurrent_received:
            messages.success(request, f"EBRT course for {patient.pt_name} saved. You can now record concurrent chemotherapy cycles in Section 4 below.")
        else:
            messages.success(request, f"EBRT course for {patient.pt_name} saved.")
        if 'save_next' in request.POST:
            return redirect('examination_detail', mr_no=patient.mr_no, enc_type='pre-brachy')
        if concurrent_received and not course_id:
            return redirect(f"/radiotherapy/{patient.mr_no}/ebrt/{course.ebrt_course_id}/edit/#concChemoContainer")
        return redirect('ebrt_edit', mr_no=patient.mr_no, course_id=course.ebrt_course_id)

    current_site_ids = [s.ebrt_site_id for s in course.sites.all()] if course else []
    if concurrent_course:
        from systemic.views import resequence_concurrent_cycles
        resequence_concurrent_cycles(concurrent_course)
        concurrent_cycles = concurrent_course.cycles.all().order_by('cycle_date', 'conc_chemo_cycle_id').prefetch_related('drugs__chemo_agent', 'drugs__dose_unit', 'drugs__chemo_route')
    else:
        concurrent_cycles = []

    from core.lookup_defaults import get_default_lookup_id
    default_intent_id = get_default_lookup_id('intent')
    default_technique_id = get_default_lookup_id('technique')
    default_machine_id = get_default_lookup_id('machine')
    default_centre_id = get_default_lookup_id('centre')

    return render(request, 'radiotherapy/ebrt_form.html', {
        'patient': patient,
        'course': course,
        'intents': intents,
        'techniques': techniques,
        'centres': centres,
        'machines': machines,
        'statuses': statuses,
        'ebrt_sites': ebrt_sites,
        'current_site_ids': current_site_ids,
        'interruption_reasons': interruption_reasons,
        'concurrent_course': concurrent_course,
        'concurrent_cycles': concurrent_cycles,
        'chemo_regimens': chemo_regimens,
        'chemo_agents': chemo_agents,
        'dose_units': dose_units,
        'chemo_routes': chemo_routes,
        'default_intent_id': default_intent_id,
        'default_technique_id': default_technique_id,
        'default_machine_id': default_machine_id,
        'default_centre_id': default_centre_id,
    })


@login_required
def ebrt_concurrent_cycle_save_view(request, mr_no, course_id, cycle_id=None):
    """
    Directly adds or updates a concurrent chemotherapy cycle and drug administration under an EBRT course.
    Enforces Validation: Concurrent date lies outside EBRT dates -> Prevent save.
    """
    if request.method != 'POST':
        return redirect('ebrt_edit', mr_no=mr_no, course_id=course_id)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(EBRTCourse, ebrt_course_id=course_id, patient=patient)

    if course.approval_locked:
        messages.error(request, "Record is locked against modifications.")
        return redirect('ebrt_edit', mr_no=patient.mr_no, course_id=course.ebrt_course_id)

    conc_course = course.concurrent_chemo_courses.first()
    if not conc_course:
        conc_course = ConcurrentChemoCourse.objects.create(
            patient=patient,
            linked_ebrt_course=course,
            concurrent_received=True,
            planned_cycles=5,
            received_cycles=5,
            entered_by=request.user.username
        )

    cycle_date = parse_date_str(request.POST.get('cycle_date'))
    if not cycle_date:
        messages.error(request, "Cycle date is mandatory.")
        return redirect('ebrt_edit', mr_no=patient.mr_no, course_id=course.ebrt_course_id)

    # Date validation: EBRT Start <= cycle_date <= EBRT End
    if not course.ebrt_start_date:
        messages.error(request, "Validation Failed: EBRT Start Date must be specified on the course before recording concurrent chemotherapy cycles.")
        return redirect('ebrt_edit', mr_no=patient.mr_no, course_id=course.ebrt_course_id)

    if course.ebrt_start_date and cycle_date < course.ebrt_start_date:
        messages.error(request, f"Validation Failed: Concurrent chemotherapy cycle date ({cycle_date.strftime('%d-%b-%Y')}) must not precede EBRT start date ({course.ebrt_start_date.strftime('%d-%b-%Y')}).")
        return redirect('ebrt_edit', mr_no=patient.mr_no, course_id=course.ebrt_course_id)

    if course.ebrt_end_date and cycle_date > course.ebrt_end_date:
        messages.error(request, f"Validation Failed: Concurrent chemotherapy cycle date ({cycle_date.strftime('%d-%b-%Y')}) must not follow EBRT end date ({course.ebrt_end_date.strftime('%d-%b-%Y')}).")
        return redirect('ebrt_edit', mr_no=patient.mr_no, course_id=course.ebrt_course_id)

    if cycle_id:
        cycle = get_object_or_404(ConcurrentChemoCycle, conc_chemo_cycle_id=cycle_id, course=conc_course)
        cycle.cycle_date = cycle_date
        cycle.cycle_status = request.POST.get('cycle_status', 'Administered')
        cycle.save()
    else:
        current_cycle_count = conc_course.cycles.count()
        received_limit = conc_course.received_cycles if (conc_course.received_cycles is not None and conc_course.received_cycles > 0) else conc_course.planned_cycles
        if received_limit is not None and current_cycle_count >= received_limit:
            messages.error(
                request,
                f"Validation Failed: Cannot add cycle #{current_cycle_count + 1}. "
                f"You have declared {received_limit} cycles administered. "
                f"Please update 'Cycles Administered' in the EBRT course record if additional cycles were given."
            )
            return redirect('ebrt_edit', mr_no=patient.mr_no, course_id=course.ebrt_course_id)

        cycle_num = current_cycle_count + 1
        cycle = ConcurrentChemoCycle.objects.create(
            course=conc_course,
            cycle_number=cycle_num,
            cycle_date=cycle_date,
            cycle_status=request.POST.get('cycle_status', 'Administered'),
            pre_cycle_notes=request.POST.get('pre_cycle_notes', ''),
            cycle_toxicity=request.POST.get('cycle_toxicity', '')
        )

    chemo_agent_id = request.POST.get('chemo_agent_id')
    if chemo_agent_id:
        dose_val = float(request.POST.get('dose')) if request.POST.get('dose') else None
        # Default dose_unit to 'mg' if not provided
        dose_unit_id = request.POST.get('dose_unit_id') or None
        if not dose_unit_id:
            mg_unit = DoseUnit.objects.filter(unit_name='mg').first()
            if mg_unit:
                dose_unit_id = mg_unit.unit_id
        no_of_days = int(request.POST.get('no_of_days') or 1)
        day_of_admin = int(request.POST.get('day_of_administration') or 1)
        chemo_route_id = request.POST.get('chemo_route_id') or None
        if cycle_id and cycle.drugs.exists():
            drug = cycle.drugs.first()
            drug.chemo_agent_id = chemo_agent_id
            drug.dose = dose_val
            drug.dose_unit_id = dose_unit_id
            drug.no_of_days = no_of_days
            drug.day_of_administration = day_of_admin
            drug.chemo_route_id = chemo_route_id
            drug.save()
        else:
            ConcurrentChemoDrug.objects.create(
                cycle=cycle,
                chemo_agent_id=chemo_agent_id,
                dose=dose_val,
                dose_unit_id=dose_unit_id,
                no_of_days=no_of_days,
                day_of_administration=day_of_admin,
                chemo_route_id=chemo_route_id,
                administered=True
            )

        # Auto-link course regimen if not already established
        if not conc_course.chemo_regimen:
            agent_obj = ChemoAgent.objects.filter(agent_id=chemo_agent_id).first()
            if agent_obj:
                if 'cisplatin' in agent_obj.agent_name.lower():
                    cis_reg = ChemoRegimen.objects.filter(regimen_code__icontains='Single-agent Cis').first() or ChemoRegimen.objects.filter(regimen_description__icontains='Cisplatin alone').first()
                    if cis_reg:
                        conc_course.chemo_regimen = cis_reg
                elif 'carboplatin' in agent_obj.agent_name.lower():
                    carbo_reg = ChemoRegimen.objects.filter(regimen_code__icontains='Single-agent Carbo').first() or ChemoRegimen.objects.filter(regimen_description__icontains='Carboplatin alone').first()
                    if carbo_reg:
                        conc_course.chemo_regimen = carbo_reg

    if conc_course.received_cycles is None:
        conc_course.received_cycles = conc_course.cycles.count()
    conc_course.save()

    from systemic.views import resequence_concurrent_cycles
    resequence_concurrent_cycles(conc_course)
    cycle.refresh_from_db()

    msg = f"Concurrent chemotherapy cycle #{cycle.cycle_number} updated (chronologically sorted)." if cycle_id else f"Concurrent chemotherapy cycle #{cycle.cycle_number} recorded (chronologically sorted)."
    messages.success(request, msg)
    return redirect('ebrt_edit', mr_no=patient.mr_no, course_id=course.ebrt_course_id)


ebrt_concurrent_cycle_add_view = ebrt_concurrent_cycle_save_view


@login_required
def ebrt_concurrent_cycle_delete_view(request, mr_no, course_id, cycle_id):
    """Deletes a concurrent chemotherapy cycle."""
    if request.method != 'POST':
        return redirect('ebrt_edit', mr_no=mr_no, course_id=course_id)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(EBRTCourse, ebrt_course_id=course_id, patient=patient)

    if course.approval_locked:
        messages.error(request, "Record is locked against modifications.")
        return redirect('ebrt_edit', mr_no=patient.mr_no, course_id=course.ebrt_course_id)

    conc_course = course.concurrent_chemo_courses.first()
    if conc_course:
        cycle = get_object_or_404(ConcurrentChemoCycle, conc_chemo_cycle_id=cycle_id, course=conc_course)
        cycle.delete()
        from systemic.views import resequence_concurrent_cycles
        resequence_concurrent_cycles(conc_course)
        conc_course.save()
        messages.success(request, "Concurrent chemotherapy cycle removed.")

    return redirect('ebrt_edit', mr_no=patient.mr_no, course_id=course.ebrt_course_id)



@login_required
def brachy_form_view(request, mr_no, course_id=None):
    """Replicates frmBrachySessions - Brachytherapy sessions & EQD2 tissue parameters."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(BrachyCourse, brachy_course_id=course_id, patient=patient) if course_id else None

    sources = BrachySourceType.objects.filter(is_active=True)
    dosings = BrachyDosing.objects.filter(is_active=True)
    centres = TreatmentCentre.objects.filter(is_active=True)
    statuses = TreatmentCourseStatus.objects.filter(is_active=True)
    applicators = BrachyApplicator.objects.filter(is_active=True)
    ebrt_courses = patient.ebrt_courses.filter(soft_deleted=False).order_by('course_sequence')

    if request.method == 'POST':
        if not course:
            course = BrachyCourse(patient=patient, entered_by=request.user.username)

        course.brachy_source_id = request.POST.get('brachy_source_id') or None
        course.brachy_dosing_id = request.POST.get('brachy_dosing_id') or None
        course.treatment_centre_id = request.POST.get('treatment_centre_id') or 1
        course.linked_ebrt_course_id = request.POST.get('linked_ebrt_course_id') or None

        course.prescription_dose_gy = float(request.POST.get('prescription_dose_gy')) if request.POST.get('prescription_dose_gy') else None
        course.total_applications_planned = int(request.POST.get('total_applications_planned')) if request.POST.get('total_applications_planned') else 2
        course.total_fractions_planned = int(request.POST.get('total_fractions_planned')) if request.POST.get('total_fractions_planned') else 4
        if course_id:
            course.total_fractions_delivered = BrachyFraction.objects.filter(brachy_session__brachy_course=course).count()
        elif request.POST.get('total_fractions_delivered'):
            course.total_fractions_delivered = int(request.POST.get('total_fractions_delivered'))
        else:
            course.total_fractions_delivered = 0

        course.brachy_start_date = request.POST.get('brachy_start_date') or None
        course.brachy_end_date = request.POST.get('brachy_end_date') or None

        course.alpha_beta_tumor = float(request.POST.get('alpha_beta_tumor') or 10.0)
        course.alpha_beta_bladder = float(request.POST.get('alpha_beta_bladder') or 3.0)
        course.alpha_beta_rectum = float(request.POST.get('alpha_beta_rectum') or 3.0)
        course.alpha_beta_sigmoid = float(request.POST.get('alpha_beta_sigmoid') or 3.0)

        is_completed = bool(request.POST.get('is_course_completed'))
        if is_completed:
            missing_errors = []
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
                    missing_errors.append(f"Session #{sess.session_number} ({sess.applicator.name}): {'; '.join(errs.values())}")
            if missing_errors:
                messages.error(request, f"Cannot mark Brachy Course Completed: {'; '.join(missing_errors)}")
                is_completed = False

        if is_completed:
            course.completion_status = 'Completed'
            completed_status = TreatmentCourseStatus.objects.filter(status_name__icontains='Completed', is_active=True).first()
            if completed_status:
                course.course_status = completed_status
        else:
            course.completion_status = request.POST.get('completion_status', 'In Progress')
            course.course_status_id = request.POST.get('course_status_id') or None

        course.completion_notes = request.POST.get('completion_notes', '')
        course.save()

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="UPDATE" if course_id else "INSERT",
            table_affected="tblBrachyCourse",
            record_ref=f"{patient.mr_no}-Brachy#{course.brachy_course_id}",
            notes=f"Saved Brachytherapy course ({course.brachy_dosing})"
        )

        messages.success(request, f"Brachytherapy course for {patient.pt_name} saved.")
        if 'add_session' in request.POST:
            return redirect('brachy_session_add', mr_no=patient.mr_no, course_id=course.brachy_course_id)
        if 'save_next' in request.POST:
            return redirect('followup_list', mr_no=patient.mr_no)
        if 'save_stay' in request.POST:
            return redirect('brachy_edit', mr_no=patient.mr_no, course_id=course.brachy_course_id)
        return redirect('radiotherapy_hub', mr_no=patient.mr_no)

    sessions = course.sessions.all().prefetch_related('fractions', 'applicator', 'image_guidance').order_by('session_number') if course else []

    # Get linked or first EBRT course for sidebar auto-population
    linked_ebrt = course.linked_ebrt_course if (course and course.linked_ebrt_course) else ebrt_courses.first()
    ebrt_dose = linked_ebrt.total_dose_gy if (linked_ebrt and linked_ebrt.total_dose_gy) else 45.0
    ebrt_fx = linked_ebrt.total_fractions if (linked_ebrt and linked_ebrt.total_fractions) else 25

    # Collect all brachy applications/fractions across sessions
    completed_fractions = []
    tumor_brachy_eqd2 = 0.0
    bladder_brachy_eqd2 = 0.0
    rectum_brachy_eqd2 = 0.0
    sigmoid_brachy_eqd2 = 0.0

    ab_tumor = course.alpha_beta_tumor if course else 10.0
    ab_bladder = course.alpha_beta_bladder if course else 3.0
    ab_rectum = course.alpha_beta_rectum if course else 3.0
    ab_sigmoid = course.alpha_beta_sigmoid if course else 3.0

    if course:
        for s in sessions:
            for fx in s.fractions.all().order_by('fraction_number_in_session', 'overall_fraction_number'):
                d_del = fx.dose_delivered_gy or fx.prescribed_dose_gy or 0.0
                hrctv = fx.hrctv_d90_gy if fx.hrctv_d90_gy is not None else d_del
                b_2cc = fx.bladder_dose_2cc_gy or 0.0
                r_2cc = fx.rectum_dose_2cc_gy or 0.0
                s_2cc = fx.sigmoid_dose_2cc_gy or 0.0

                # Compute fraction EQD2
                fx_t_eqd2 = BrachyFraction.calculate_eqd2(hrctv, 1, ab_tumor) if hrctv else 0.0
                fx_b_eqd2 = BrachyFraction.calculate_eqd2(b_2cc, 1, ab_bladder) if b_2cc else 0.0
                fx_r_eqd2 = BrachyFraction.calculate_eqd2(r_2cc, 1, ab_rectum) if r_2cc else 0.0
                fx_s_eqd2 = BrachyFraction.calculate_eqd2(s_2cc, 1, ab_sigmoid) if s_2cc else 0.0

                tumor_brachy_eqd2 += fx_t_eqd2
                bladder_brachy_eqd2 += fx_b_eqd2
                rectum_brachy_eqd2 += fx_r_eqd2
                sigmoid_brachy_eqd2 += fx_s_eqd2

                completed_fractions.append({
                    'fraction_id': fx.brachy_fraction_id,
                    'session_id': s.brachy_session_id,
                    'session_num': s.session_number,
                    'overall_num': fx.overall_fraction_number,
                    'fraction_num_in_session': fx.fraction_number_in_session,
                    'fraction_date': fx.fraction_date,
                    'dose_delivered': d_del,
                    'hrctv_d90': hrctv,
                    'bladder_2cc': b_2cc,
                    'rectum_2cc': r_2cc,
                    'sigmoid_2cc': s_2cc,
                    'tumor_eqd2': round(fx_t_eqd2, 2),
                    'bladder_eqd2': round(fx_b_eqd2, 2),
                    'rectum_eqd2': round(fx_r_eqd2, 2),
                    'sigmoid_eqd2': round(fx_s_eqd2, 2),
                })

    # Compute baseline EBRT EQD2
    ebrt_tumor_eqd2 = BrachyFraction.calculate_eqd2(ebrt_dose, ebrt_fx, ab_tumor) if (ebrt_dose and ebrt_fx) else 0.0
    ebrt_bladder_eqd2 = BrachyFraction.calculate_eqd2(ebrt_dose, ebrt_fx, ab_bladder) if (ebrt_dose and ebrt_fx) else 0.0
    ebrt_rectum_eqd2 = BrachyFraction.calculate_eqd2(ebrt_dose, ebrt_fx, ab_rectum) if (ebrt_dose and ebrt_fx) else 0.0
    ebrt_sigmoid_eqd2 = BrachyFraction.calculate_eqd2(ebrt_dose, ebrt_fx, ab_sigmoid) if (ebrt_dose and ebrt_fx) else 0.0

    cumulative_tumor_eqd2 = round(ebrt_tumor_eqd2 + tumor_brachy_eqd2, 1)
    cumulative_bladder_eqd2 = round(ebrt_bladder_eqd2 + bladder_brachy_eqd2, 1)
    cumulative_rectum_eqd2 = round(ebrt_rectum_eqd2 + rectum_brachy_eqd2, 1)
    cumulative_sigmoid_eqd2 = round(ebrt_sigmoid_eqd2 + sigmoid_brachy_eqd2, 1)

    from core.lookup_defaults import get_default_lookup_id
    default_centre_id = get_default_lookup_id('centre')

    return render(request, 'radiotherapy/brachy_form.html', {
        'patient': patient,
        'course': course,
        'sources': sources,
        'dosings': dosings,
        'centres': centres,
        'statuses': statuses,
        'applicators': applicators,
        'ebrt_courses': ebrt_courses,
        'sessions': sessions,
        'linked_ebrt': linked_ebrt,
        'ebrt_dose': ebrt_dose,
        'ebrt_fx': ebrt_fx,
        'completed_fractions': completed_fractions,
        'ebrt_tumor_eqd2': round(ebrt_tumor_eqd2, 1),
        'ebrt_bladder_eqd2': round(ebrt_bladder_eqd2, 1),
        'ebrt_rectum_eqd2': round(ebrt_rectum_eqd2, 1),
        'ebrt_sigmoid_eqd2': round(ebrt_sigmoid_eqd2, 1),
        'tumor_brachy_eqd2': round(tumor_brachy_eqd2, 1),
        'bladder_brachy_eqd2': round(bladder_brachy_eqd2, 1),
        'rectum_brachy_eqd2': round(rectum_brachy_eqd2, 1),
        'sigmoid_brachy_eqd2': round(sigmoid_brachy_eqd2, 1),
        'cumulative_tumor_eqd2': cumulative_tumor_eqd2,
        'cumulative_bladder_eqd2': cumulative_bladder_eqd2,
        'cumulative_rectum_eqd2': cumulative_rectum_eqd2,
        'cumulative_sigmoid_eqd2': cumulative_sigmoid_eqd2,
        'default_centre_id': default_centre_id,
    })


@login_required
def brachy_session_form_view(request, mr_no, course_id, session_id=None):
    """Replicates frmBrachySessions - Insertion session and fraction dosimetry."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(BrachyCourse, brachy_course_id=course_id, patient=patient)
    session = get_object_or_404(BrachySession, brachy_session_id=session_id, brachy_course=course) if session_id else None

    # Check approval lock
    if session and session.approval_locked and request.method == 'POST':
        messages.error(request, "This brachy application is approved and locked. Unapprove the course before editing.")
        return redirect('brachy_edit', mr_no=patient.mr_no, course_id=course.brachy_course_id)

    applicators = ApplicatorType.objects.filter(active=True).order_by('display_order', 'name')
    guidances = BrachyImageGuidance.objects.filter(is_active=True)
    sources = BrachySourceType.objects.filter(is_active=True)
    dosings = BrachyDosing.objects.filter(is_active=True)
    anaesthesias = AnaesthesiaType.objects.filter(is_active=True)
    session_statuses = BrachySessionStatus.objects.filter(is_active=True)
    fraction = session.fractions.first() if session else None

    form_errors = {}
    if request.method == 'POST':
        form = BrachySessionForm(request.POST, instance=session, course=course)
        if form.is_valid():
            session = form.save(commit=False)
            session.brachy_course = course
            session.save()

            # Sync dosing and source to course if not set on course
            if session.brachy_dosing and not course.brachy_dosing:
                course.brachy_dosing = session.brachy_dosing
            if session.brachy_source and not course.brachy_source:
                course.brachy_source = session.brachy_source
            course.save()

            # Update or create fraction dosimetry
            if not fraction:
                fraction = BrachyFraction(
                    brachy_session=session,
                    overall_fraction_number=course.total_fractions_delivered + 1
                )

            fraction.fraction_date = session.session_date
            fraction.prescribed_dose_gy = float(request.POST.get('dose_delivered_gy')) if request.POST.get('dose_delivered_gy') else None
            fraction.dose_delivered_gy = float(request.POST.get('dose_delivered_gy')) if request.POST.get('dose_delivered_gy') else None
            fraction.total_dwell_time_seconds = float(request.POST.get('total_dwell_time_seconds') or 0)

            # OAR doses (2cc)
            fraction.bladder_dose_2cc_gy = float(request.POST.get('bladder_dose_2cc_gy')) if request.POST.get('bladder_dose_2cc_gy') else None
            fraction.rectum_dose_2cc_gy = float(request.POST.get('rectum_dose_2cc_gy')) if request.POST.get('rectum_dose_2cc_gy') else None
            fraction.sigmoid_dose_2cc_gy = float(request.POST.get('sigmoid_dose_2cc_gy')) if request.POST.get('sigmoid_dose_2cc_gy') else None

            # Target coverage
            fraction.hrctv_d90_gy = float(request.POST.get('hrctv_d90_gy')) if request.POST.get('hrctv_d90_gy') else None
            fraction.hrctv_d98_gy = float(request.POST.get('hrctv_d98_gy')) if request.POST.get('hrctv_d98_gy') else None
            fraction.volume_hrctv_cc = float(request.POST.get('volume_hrctv_cc')) if request.POST.get('volume_hrctv_cc') else None
            fraction.save()

            # Update delivered count on course
            course.total_fractions_delivered = BrachyFraction.objects.filter(brachy_session__brachy_course=course).count()
            course.save()

            AuditLog.objects.create(
                username=request.user.username,
                full_name=request.user.first_name,
                action="UPDATE" if session_id else "INSERT",
                table_affected="tblBrachySessions",
                record_ref=f"Session#{session.brachy_session_id}",
                notes=f"Saved brachy application #{session.session_number}: {session.applicator}"
            )

            messages.success(request, f"Brachy application #{session.session_number} saved.")
            return redirect('brachy_edit', mr_no=patient.mr_no, course_id=course.brachy_course_id)
        else:
            form_errors = form.errors
            for field, err_list in form.errors.items():
                for err in err_list:
                    messages.error(request, f"{err}")
    else:
        form = BrachySessionForm(instance=session, course=course)

    # Build applicator rules dictionary for instant client-side dynamic validation
    rules_dict = {}
    for app in applicators:
        app_rules = []
        for r in app.field_rules.select_related('measurement_definition').order_by('display_order', 'id'):
            if r.measurement_definition.active:
                app_rules.append({
                    'code': r.measurement_definition.code,
                    'label': r.measurement_definition.label,
                    'enabled': r.enabled,
                    'required': r.required,
                    'unit': r.measurement_definition.unit,
                    'min_value': r.get_minimum_value(),
                    'max_value': r.get_maximum_value(),
                    'data_type': r.measurement_definition.data_type,
                    'display_order': r.display_order,
                })
        rules_dict[str(app.id)] = app_rules

    from core.lookup_defaults import get_default_lookup_id
    default_guidance_id = get_default_lookup_id('guidance')
    default_dosing_id = get_default_lookup_id('dosing')
    default_source_id = get_default_lookup_id('source')
    default_anaesthesia_id = get_default_lookup_id('anaesthesia')
    default_applicator_id = get_default_lookup_id('applicator')

    return render(request, 'radiotherapy/brachy_session_form.html', {
        'patient': patient,
        'course': course,
        'session': session,
        'form': form,
        'form_errors': form_errors,
        'fraction': fraction,
        'applicators': applicators,
        'guidances': guidances,
        'sources': sources,
        'dosings': dosings,
        'anaesthesias': anaesthesias,
        'session_statuses': session_statuses,
        'applicator_rules_json': json.dumps(rules_dict),
        'default_guidance_id': default_guidance_id,
        'default_dosing_id': default_dosing_id,
        'default_source_id': default_source_id,
        'default_anaesthesia_id': default_anaesthesia_id,
        'default_applicator_id': default_applicator_id,
    })


@login_required
def api_applicator_rules_view(request, applicator_id=None):
    """
    JSON API endpoint returning active measurement rules for an applicator type.
    """
    if applicator_id:
        applicator = get_object_or_404(ApplicatorType, id=applicator_id)
        rules = []
        for r in applicator.field_rules.select_related('measurement_definition').order_by('display_order', 'id'):
            if r.measurement_definition.active:
                rules.append({
                    'code': r.measurement_definition.code,
                    'label': r.measurement_definition.label,
                    'enabled': r.enabled,
                    'required': r.required,
                    'unit': r.measurement_definition.unit,
                    'min_value': r.get_minimum_value(),
                    'max_value': r.get_maximum_value(),
                    'data_type': r.measurement_definition.data_type,
                    'display_order': r.display_order,
                })
        return JsonResponse({
            'applicator_id': applicator.id,
            'applicator_name': applicator.name,
            'rules': rules
        })
    else:
        data = {}
        for app in ApplicatorType.objects.filter(active=True):
            rules = []
            for r in app.field_rules.select_related('measurement_definition').order_by('display_order', 'id'):
                if r.measurement_definition.active:
                    rules.append({
                        'code': r.measurement_definition.code,
                        'label': r.measurement_definition.label,
                        'enabled': r.enabled,
                        'required': r.required,
                        'unit': r.measurement_definition.unit,
                        'min_value': r.get_minimum_value(),
                        'max_value': r.get_maximum_value(),
                        'data_type': r.measurement_definition.data_type,
                        'display_order': r.display_order,
                    })
            data[str(app.id)] = {
                'applicator_id': app.id,
                'applicator_name': app.name,
                'rules': rules
            }
        return JsonResponse(data)


@login_required
def applicator_rules_admin_view(request):
    """
    Dedicated administration form for configuring Applicator Types and Field Activation/Validation Rules.
    Restricted to administrator accounts.
    """
    if not is_admin_user(request.user):
        messages.error(request, "Permission Denied: Only administrators can configure applicator measurement rules.")
        return redirect('dashboard')

    applicators = ApplicatorType.objects.all().order_by('display_order', 'id')
    measurement_defs = ApplicatorMeasurementDefinition.objects.all().order_by('display_order', 'id')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_rules':
            updated_count = 0
            for app in applicators:
                for mdef in measurement_defs:
                    rule = ApplicatorFieldRule.objects.filter(
                        applicator_type=app,
                        measurement_definition=mdef
                    ).first()
                    prefix = f"rule_{app.id}_{mdef.id}_"
                    enabled_val = bool(request.POST.get(prefix + 'enabled'))
                    required_val = bool(request.POST.get(prefix + 'required'))
                    order_val = int(request.POST.get(prefix + 'order') or mdef.display_order)
                    min_val = request.POST.get(prefix + 'min', '').strip()
                    max_val = request.POST.get(prefix + 'max', '').strip()

                    min_override = float(min_val) if min_val else None
                    max_override = float(max_val) if max_val else None

                    if not rule:
                        rule = ApplicatorFieldRule.objects.create(
                            applicator_type=app,
                            measurement_definition=mdef,
                            enabled=enabled_val,
                            required=required_val,
                            display_order=order_val,
                            min_value_override=min_override,
                            max_value_override=max_override
                        )
                    else:
                        rule.enabled = enabled_val
                        rule.required = required_val
                        rule.display_order = order_val
                        rule.min_value_override = min_override
                        rule.max_value_override = max_override
                        rule.save()
                    updated_count += 1

            AuditLog.objects.create(
                username=request.user.username,
                full_name=request.user.get_full_name(),
                action="UPDATE",
                table_affected="sbtblApplicatorFieldRule",
                record_ref="ApplicatorRulesConfig",
                notes=f"Updated applicator measurement rules configuration by {request.user.username}"
            )
            messages.success(request, "Applicator measurement rules updated successfully.")
            return redirect('applicator_rules_admin')

        elif action == 'add_applicator':
            app_name = request.POST.get('new_applicator_name', '').strip()
            app_order = int(request.POST.get('new_applicator_order') or 1)
            if app_name:
                from django.db.models import Max
                max_id = ApplicatorType.objects.aggregate(m=Max('id'))['m'] or 0
                new_app = ApplicatorType.objects.create(
                    id=max_id + 1,
                    name=app_name,
                    active=True,
                    display_order=app_order
                )
                for idx, mdef in enumerate(measurement_defs, start=1):
                    ApplicatorFieldRule.objects.create(
                        applicator_type=new_app,
                        measurement_definition=mdef,
                        enabled=False,
                        required=False,
                        display_order=idx
                    )
                messages.success(request, f"New applicator '{app_name}' created. Configure its measurement rules below.")
            return redirect('applicator_rules_admin')

        elif action == 'toggle_applicator':
            app_id = request.POST.get('applicator_id')
            app = get_object_or_404(ApplicatorType, id=app_id)
            app.active = not app.active
            app.save()
            status_str = "activated" if app.active else "deactivated"
            messages.info(request, f"Applicator '{app.name}' has been {status_str}.")
            return redirect('applicator_rules_admin')

    # Build matrix of applicator -> measurements
    matrix = []
    for app in applicators:
        app_rules_map = {r.measurement_definition_id: r for r in app.field_rules.all()}
        meas_list = []
        for mdef in measurement_defs:
            rule = app_rules_map.get(mdef.id)
            meas_list.append({
                'mdef': mdef,
                'rule': rule,
                'enabled': rule.enabled if rule else False,
                'required': rule.required if rule else False,
                'order': rule.display_order if rule else mdef.display_order,
                'min': rule.min_value_override if (rule and rule.min_value_override is not None) else '',
                'max': rule.max_value_override if (rule and rule.max_value_override is not None) else '',
            })
        matrix.append({
            'applicator': app,
            'measurements': meas_list
        })

    return render(request, 'radiotherapy/applicator_rules_admin.html', {
        'matrix': matrix,
        'measurement_defs': measurement_defs,
    })


@login_required
def brachy_application_save_view(request, mr_no, course_id, session_id, fraction_id=None):
    """
    Directly adds or updates a brachytherapy application (fraction) under a session.
    Allows multiple applications per insertion session with separate doses.
    """
    if request.method != 'POST':
        return redirect('brachy_edit', mr_no=mr_no, course_id=course_id)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(BrachyCourse, brachy_course_id=course_id, patient=patient)
    session = get_object_or_404(BrachySession, brachy_session_id=session_id, brachy_course=course)

    if fraction_id:
        fraction = get_object_or_404(BrachyFraction, brachy_fraction_id=fraction_id, brachy_session=session)
    else:
        total_in_course = BrachyFraction.objects.filter(brachy_session__brachy_course=course).count()
        total_in_session = session.fractions.count()
        fraction = BrachyFraction(
            brachy_session=session,
            fraction_number_in_session=total_in_session + 1,
            overall_fraction_number=total_in_course + 1
        )

    f_date = parse_date_str(request.POST.get('fraction_date')) or session.session_date
    if not f_date:
        messages.error(request, "A valid application date is required.")
        return redirect('brachy_edit', mr_no=patient.mr_no, course_id=course.brachy_course_id)

    from datetime import date
    if f_date > date.today():
        messages.error(request, f"Application date ({f_date.strftime('%d-%b-%Y')}) cannot be a future date.")
        return redirect('brachy_edit', mr_no=patient.mr_no, course_id=course.brachy_course_id)

    if session.session_date and f_date < session.session_date:
        messages.error(request, f"Application date ({f_date.strftime('%d-%b-%Y')}) cannot be before the session insertion date ({session.session_date.strftime('%d-%b-%Y')}).")
        return redirect('brachy_edit', mr_no=patient.mr_no, course_id=course.brachy_course_id)

    fraction.fraction_date = f_date
    fraction.dose_delivered_gy = float(request.POST.get('dose_delivered_gy')) if request.POST.get('dose_delivered_gy') else 0.0
    fraction.prescribed_dose_gy = fraction.dose_delivered_gy
    fraction.total_dwell_time_seconds = float(request.POST.get('total_dwell_time_seconds') or 0.0)

    fraction.hrctv_d90_gy = float(request.POST.get('hrctv_d90_gy')) if request.POST.get('hrctv_d90_gy') else None
    fraction.volume_hrctv_cc = float(request.POST.get('volume_hrctv_cc')) if request.POST.get('volume_hrctv_cc') else None
    fraction.bladder_dose_2cc_gy = float(request.POST.get('bladder_dose_2cc_gy')) if request.POST.get('bladder_dose_2cc_gy') else None
    fraction.rectum_dose_2cc_gy = float(request.POST.get('rectum_dose_2cc_gy')) if request.POST.get('rectum_dose_2cc_gy') else None
    fraction.sigmoid_dose_2cc_gy = float(request.POST.get('sigmoid_dose_2cc_gy')) if request.POST.get('sigmoid_dose_2cc_gy') else None
    fraction.fraction_notes = request.POST.get('fraction_notes', '')
    fraction.save()

    # Update course delivered fractions count
    course.total_fractions_delivered = BrachyFraction.objects.filter(brachy_session__brachy_course=course).count()
    if not course.brachy_start_date:
        course.brachy_start_date = f_date
    course.brachy_end_date = f_date
    course.save()

    AuditLog.objects.create(
        username=request.user.username,
        full_name=request.user.first_name,
        action="UPDATE" if fraction_id else "INSERT",
        table_affected="tblBrachyFractions",
        record_ref=f"Fraction#{fraction.brachy_fraction_id}",
        notes=f"Saved brachy application #{fraction.overall_fraction_number}: {fraction.dose_delivered_gy} Gy ({fraction.fraction_date})"
    )

    messages.success(request, f"Brachytherapy Application #{fraction.overall_fraction_number} ({fraction.dose_delivered_gy} Gy) saved.")
    return redirect('brachy_edit', mr_no=patient.mr_no, course_id=course.brachy_course_id)


@login_required
def ebrt_course_delete_view(request, mr_no, course_id):
    """Allows administrators to delete (soft-delete) an EBRT course."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Permission denied: Administrator privileges required to delete an EBRT course.")
        return redirect('radiotherapy_hub', mr_no=mr_no)

    if request.method != 'POST':
        return redirect('radiotherapy_hub', mr_no=mr_no)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(EBRTCourse, ebrt_course_id=course_id, patient=patient)
    seq = course.course_sequence
    course.soft_deleted = True
    course.save()

    AuditLog.objects.create(
        username=request.user.username,
        full_name=request.user.first_name,
        action="DELETE",
        table_affected="tblEBRTCourse",
        record_ref=f"EBRT#{course.ebrt_course_id}",
        notes=f"Deleted EBRT Course #{seq} for patient {patient.mr_no}"
    )

    messages.success(request, f"EBRT Course #{seq} deleted.")
    return redirect('radiotherapy_hub', mr_no=patient.mr_no)


@login_required
def brachy_course_delete_view(request, mr_no, course_id):
    """Allows administrators to delete (soft-delete) a Brachytherapy course."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Permission denied: Administrator privileges required to delete a Brachytherapy course.")
        return redirect('radiotherapy_hub', mr_no=mr_no)

    if request.method != 'POST':
        return redirect('radiotherapy_hub', mr_no=mr_no)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(BrachyCourse, brachy_course_id=course_id, patient=patient)
    seq = course.course_sequence
    course.soft_deleted = True
    course.save()

    AuditLog.objects.create(
        username=request.user.username,
        full_name=request.user.first_name,
        action="DELETE",
        table_affected="tblBrachyCourse",
        record_ref=f"Brachy#{course.brachy_course_id}",
        notes=f"Deleted Brachytherapy Course #{seq} for patient {patient.mr_no}"
    )

    messages.success(request, f"Brachytherapy Course #{seq} deleted.")
    return redirect('radiotherapy_hub', mr_no=patient.mr_no)


@login_required
def brachy_application_delete_view(request, mr_no, course_id, session_id, fraction_id):
    """Deletes a brachy fraction."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Permission denied: Administrator privileges required to delete a Brachy fraction.")
        return redirect('brachy_edit', mr_no=mr_no, course_id=course_id)

    if request.method != 'POST':
        return redirect('brachy_edit', mr_no=mr_no, course_id=course_id)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(BrachyCourse, brachy_course_id=course_id, patient=patient)
    session = get_object_or_404(BrachySession, brachy_session_id=session_id, brachy_course=course)
    fraction = get_object_or_404(BrachyFraction, brachy_fraction_id=fraction_id, brachy_session=session)

    f_num = fraction.overall_fraction_number
    fraction.delete()

    course.total_fractions_delivered = BrachyFraction.objects.filter(brachy_session__brachy_course=course).count()
    course.save()

    AuditLog.objects.create(
        username=request.user.username,
        full_name=request.user.first_name,
        action="DELETE",
        table_affected="tblBrachyFractions",
        record_ref=f"Fraction#{fraction_id}",
        notes=f"Deleted brachy fraction #{f_num} from Application #{session.session_number}"
    )

    messages.success(request, f"Brachy fraction #{f_num} deleted.")
    return redirect('brachy_edit', mr_no=patient.mr_no, course_id=course.brachy_course_id)


@login_required
def brachy_session_delete_view(request, mr_no, course_id, session_id):
    """Deletes an entire brachy application and its fractions."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Permission denied: Administrator privileges required to delete a Brachy application.")
        return redirect('brachy_edit', mr_no=mr_no, course_id=course_id)

    if request.method != 'POST':
        return redirect('brachy_edit', mr_no=mr_no, course_id=course_id)

    patient = get_object_or_404(Patient, mr_no=mr_no)
    course = get_object_or_404(BrachyCourse, brachy_course_id=course_id, patient=patient)
    session = get_object_or_404(BrachySession, brachy_session_id=session_id, brachy_course=course)

    s_num = session.session_number
    session.delete()

    course.total_fractions_delivered = BrachyFraction.objects.filter(brachy_session__brachy_course=course).count()
    course.save()

    AuditLog.objects.create(
        username=request.user.username,
        full_name=request.user.first_name,
        action="DELETE",
        table_affected="tblBrachySessions",
        record_ref=f"Session#{session_id}",
        notes=f"Deleted brachy application #{s_num}"
    )

    messages.success(request, f"Brachy application #{s_num} deleted.")
    return redirect('brachy_edit', mr_no=patient.mr_no, course_id=course.brachy_course_id)
