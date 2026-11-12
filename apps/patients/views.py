from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q

from patients.models import Patient
from core.models import State, District, Consultant, AuditLog

@login_required
def patient_register_view(request):
    """Replicates frmPatientReg in DataEntry/New record mode."""
    states = State.objects.all()
    districts = District.objects.all()
    consultants = Consultant.objects.filter(is_active=True)

    if request.method == 'POST':
        mr_no = request.POST.get('mr_no', '').strip()
        pt_name = request.POST.get('pt_name', '').strip()
        phone = request.POST.get('phone', '').strip()

        if not mr_no or not pt_name or not phone:
            messages.error(request, "MR No., Patient Name, and Phone are required fields.")
            return render(request, 'patients/patient_form.html', {
                'states': states, 'districts': districts, 'consultants': consultants,
                'is_new': True
            })

        if Patient.objects.filter(mr_no=mr_no).exists():
            messages.error(request, f"Patient with MR No. '{mr_no}' already exists in database.")
            return render(request, 'patients/patient_form.html', {
                'states': states, 'districts': districts, 'consultants': consultants,
                'is_new': True
            })

        pt = Patient(
            mr_no=mr_no,
            pt_name=pt_name,
            sex=request.POST.get('sex', 'Female'),
            date_of_birth=request.POST.get('date_of_birth') or None,
            dob_is_estimated=bool(request.POST.get('dob_is_estimated')),
            date_of_registration=request.POST.get('date_of_registration') or None,
            phone=phone,
            phone_alternate=request.POST.get('phone_alternate', ''),
            address=request.POST.get('address', ''),
            state_id=request.POST.get('state_id') or None,
            district_id=request.POST.get('district_id') or None,
            pincode=request.POST.get('pincode', ''),
            digipin=request.POST.get('digipin', ''),
            country=request.POST.get('country', 'India'),
            primary_consultant_id=request.POST.get('consultant_id') or None,
            notes=request.POST.get('notes', ''),
            entered_by=request.user.username,
        )
        pt.save()

        # Audit Log
        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="INSERT",
            table_affected="tblPtDetails",
            record_ref=pt.mr_no,
            notes="Registered new patient record"
        )

        messages.success(request, f"Patient '{pt.pt_name}' [{pt.mr_no}] registered successfully!")
        if 'save_next' in request.POST:
            return redirect('history_detail', mr_no=pt.mr_no)
        return redirect('dashboard')

    return render(request, 'patients/patient_form.html', {
        'states': states, 'districts': districts, 'consultants': consultants,
        'is_new': True
    })

@login_required
def patient_edit_view(request, mr_no):
    """Replicates frmPatientReg in Edit mode."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    states = State.objects.all()
    districts = District.objects.all()
    consultants = Consultant.objects.filter(is_active=True)

    if request.method == 'POST':
        patient.pt_name = request.POST.get('pt_name', patient.pt_name)
        patient.sex = request.POST.get('sex', patient.sex)
        patient.date_of_birth = request.POST.get('date_of_birth') or None
        patient.dob_is_estimated = bool(request.POST.get('dob_is_estimated'))
        patient.date_of_registration = request.POST.get('date_of_registration') or patient.date_of_registration
        patient.phone = request.POST.get('phone', patient.phone)
        patient.phone_alternate = request.POST.get('phone_alternate', '')
        patient.address = request.POST.get('address', '')
        patient.state_id = request.POST.get('state_id') or None
        patient.district_id = request.POST.get('district_id') or None
        patient.pincode = request.POST.get('pincode', '')
        patient.digipin = request.POST.get('digipin', '')
        patient.country = request.POST.get('country', 'India')
        patient.primary_consultant_id = request.POST.get('consultant_id') or None
        patient.notes = request.POST.get('notes', '')
        patient.last_modified_by = request.user.username
        patient.save()

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="UPDATE",
            table_affected="tblPtDetails",
            record_ref=patient.mr_no,
            notes="Updated demographics"
        )

        messages.success(request, f"Patient demographics for '{patient.pt_name}' updated successfully.")
        if 'save_next' in request.POST:
            return redirect('history_detail', mr_no=patient.mr_no)
        return redirect('dashboard')

    return render(request, 'patients/patient_form.html', {
        'patient': patient, 'states': states, 'districts': districts,
        'consultants': consultants, 'is_new': False
    })

@login_required
def patient_search_view(request):
    """Replicates frmPatientSearch."""
    q = request.GET.get('q', '').strip()
    patients = []
    if q:
        patients = Patient.objects.filter(
            Q(mr_no__icontains=q) | Q(pt_name__icontains=q) | Q(phone__icontains=q),
            soft_deleted=False
        )
    return render(request, 'patients/patient_search.html', {'patients': patients, 'query': q})

@login_required
def patient_summary_view(request, mr_no):
    """Replicates rptPatientSummary and Access PS_FullSummary multi-module overview."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    diagnoses = patient.diagnoses.filter(soft_deleted=False)
    histories = patient.histories.filter(soft_deleted=False)
    encounters = patient.encounters.filter(soft_deleted=False).prefetch_related('svg_findings__region')
    blood_labs = patient.blood_tests.filter(soft_deleted=False)
    path_reports = patient.pathology_reports.filter(soft_deleted=False)
    imaging_studies = patient.imaging_studies.filter(soft_deleted=False)
    molecular_tests = patient.molecular_tests.filter(soft_deleted=False)
    
    # Radiotherapy with targets resolved and indented concurrent chemotherapy
    ebrt_courses = patient.ebrt_courses.filter(soft_deleted=False).prefetch_related(
        'sites__ebrt_site', 'interruptions__interruption_reason',
        'concurrent_chemo_courses__cycles__drugs__chemo_agent',
        'concurrent_chemo_courses__cycles__drugs__dose_unit',
        'concurrent_chemo_courses__cycles__drugs__chemo_route'
    )
    brachy_courses = patient.brachy_courses.filter(soft_deleted=False).prefetch_related('sessions__fractions')
    
    # NACT grouped by course and cycle
    nact_courses = patient.nact_courses.filter(soft_deleted=False).exclude(nact_received=False, treatment_status='PLANNED').prefetch_related(
        'cycles__drugs__chemo_agent', 'cycles__drugs__dose_unit', 'cycles__drugs__chemo_route'
    )
    
    # Adjuvant: omitted if planned and not given
    adjuvant_courses = patient.adjuvant_courses.filter(soft_deleted=False).exclude(adjuvant_received=False, treatment_status='PLANNED').prefetch_related(
        'cycles__drugs__chemo_agent', 'cycles__drugs__dose_unit', 'cycles__drugs__chemo_route'
    )
    
    followups = patient.follow_up_records.filter(soft_deleted=False)
    documents = patient.documents.all()

    return render(request, 'patients/patient_summary.html', {
        'patient': patient,
        'diagnoses': diagnoses,
        'histories': histories,
        'encounters': encounters,
        'blood_labs': blood_labs,
        'path_reports': path_reports,
        'imaging_studies': imaging_studies,
        'molecular_tests': molecular_tests,
        'ebrt_courses': ebrt_courses,
        'brachy_courses': brachy_courses,
        'nact_courses': nact_courses,
        'adjuvant_courses': adjuvant_courses,
        'followups': followups,
        'documents': documents,
    })


@login_required
def patient_summary_pdf_view(request, mr_no):
    """Generates an A4 Clinical Summary PDF for the patient."""
    from .pdf_summary import build_patient_summary_pdf
    from django.http import HttpResponse

    patient = get_object_or_404(Patient, mr_no=mr_no)
    pdf_buffer = build_patient_summary_pdf(patient)

    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    safe_name = patient.pt_name.replace(' ', '_')
    response['Content-Disposition'] = f'inline; filename="Clinical_Summary_{patient.mr_no}_{safe_name}.pdf"'
    return response


from core.permissions import can_delete_patient

@login_required
def patient_delete_view(request, mr_no):
    """Allows administrators to delete (soft-delete) a patient record."""
    if not can_delete_patient(request.user):
        messages.error(request, "Permission denied: Administrator privileges required to delete patient records.")
        return redirect('dashboard')

    patient = get_object_or_404(Patient, mr_no=mr_no)

    if request.method == 'POST':
        patient_name = patient.pt_name
        patient.soft_deleted = True
        patient.save()

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="DELETE",
            table_affected="tblPatient",
            record_ref=mr_no,
            notes=f"Soft-deleted patient record {patient_name} (MR: {mr_no})"
        )

        messages.success(request, f"Patient {patient_name} (MR: {mr_no}) deleted successfully.")
        return redirect('dashboard')

    return render(request, 'patients/patient_confirm_delete.html', {
        'patient': patient
    })


@login_required
def patient_dashboard_view(request, mr_no):
    from core.views import dashboard_view
    return dashboard_view(request, mr_no=mr_no)
