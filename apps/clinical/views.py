from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import date

from patients.models import Patient
from core.models import AuditLog
from clinical.models import (
    ClinicalHistory, Diagnosis, Encounter, EncounterType, ECOGScore,
    PrimarySite, Histology, Grade, StagingSystem, BasisOfDiagnosis,
    SVGRegion, ClinicalSVGFinding
)

@login_required
def history_detail_view(request, mr_no):
    """Replicates frmHistory - Medical, surgical, comorbidities and habits history."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    history = patient.histories.filter(soft_deleted=False).first()

    if request.method == 'POST':
        if not history:
            history = ClinicalHistory(patient=patient, entered_by=request.user.username)

        history.snapshot_date = request.POST.get('snapshot_date') or date.today()
        history.hpi = request.POST.get('hpi', '')
        history.past_med_surg = request.POST.get('past_med_surg', '')

        # Comorbidities
        history.hypertension = bool(request.POST.get('hypertension'))
        history.hypothyroidism = bool(request.POST.get('hypothyroidism'))
        history.seizures = bool(request.POST.get('seizures'))
        history.diabetic = bool(request.POST.get('diabetic'))
        history.comorbidity_others = bool(request.POST.get('comorbidity_others'))
        history.comorbidity_notes = request.POST.get('comorbidity_notes', '')

        # Habits
        history.smoking = bool(request.POST.get('smoking'))
        history.alcohol = bool(request.POST.get('alcohol'))
        history.tobacco_chewing = bool(request.POST.get('tobacco_chewing'))
        history.habits_others = bool(request.POST.get('habits_others'))
        history.habits_notes = request.POST.get('habits_notes', '')

        # Presenting Symptoms
        history.bleeding_pv = bool(request.POST.get('bleeding_pv'))
        history.water_discharge_pv = bool(request.POST.get('water_discharge_pv'))
        history.dyspareunia = bool(request.POST.get('dyspareunia'))
        history.loin_pain = bool(request.POST.get('loin_pain'))

        # Prior Treatments
        history.prior_radiation = bool(request.POST.get('prior_radiation'))
        history.prior_radiation_details = request.POST.get('prior_radiation_details', '')
        history.previous_surgery = bool(request.POST.get('previous_surgery'))
        history.previous_surgery_details = request.POST.get('previous_surgery_details', '')

        history.last_modified_by = request.user.username
        history.save()

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="UPDATE" if history.history_id else "INSERT",
            table_affected="tblHistory",
            record_ref=f"{patient.mr_no}-Hist#{history.history_id}",
            notes="Saved clinical history record"
        )

        messages.success(request, f"Clinical history for {patient.pt_name} saved successfully.")
        if 'save_next' in request.POST:
            return redirect('examination_detail', mr_no=patient.mr_no, enc_type='baseline')
        return redirect('dashboard')

    return render(request, 'clinical/history_form.html', {
        'patient': patient,
        'history': history,
    })


def detect_grade_from_text(text):
    """Auto-detects WHO/FIGO tumour grade from pathology impression or description."""
    if not text:
        return None
    t = text.lower()
    import re
    if re.search(r'\b(g4|grade\s*4|undifferentiated)\b', t):
        return 5  # G4 - Undifferentiated
    if re.search(r'\b(g3|grade\s*3|poorly\s+diff|poorly\s+differentiated|high\s+grade)\b', t):
        return 4  # G3 - Poorly differentiated
    if re.search(r'\b(g2|grade\s*2|mod(erately)?\s+diff|moderately\s+differentiated|intermediate\s+grade)\b', t):
        return 3  # G2 - Moderately differentiated
    if re.search(r'\b(g1|grade\s*1|well\s+diff|well\s+differentiated|low\s+grade)\b', t):
        return 2  # G1 - Well differentiated
    return None


@login_required
def diagnosis_detail_view(request, mr_no, diagnosis_id=None):
    """
    Replicates frmDiagnosis - Primary tumor site, histology, grade, stage and full diagnosis.
    Supports multiple diagnoses per patient, with histologic type and grade auto-populated
    from pathology and molecular investigation reports.
    """
    patient = get_object_or_404(Patient, mr_no=mr_no)
    all_diagnoses = patient.diagnoses.filter(soft_deleted=False).order_by('-is_current', 'diagnosis_sequence', '-date_of_diagnosis')

    is_new = (request.GET.get('action') == 'new')
    selected_diag_id = diagnosis_id or request.GET.get('diag_id')

    if is_new:
        diagnosis = None
    elif selected_diag_id:
        diagnosis = patient.diagnoses.filter(pk=selected_diag_id, soft_deleted=False).first()
    else:
        diagnosis = all_diagnoses.first()

    sites = PrimarySite.objects.filter(is_active=True)
    histologies = Histology.objects.filter(is_active=True)
    grades = Grade.objects.filter(is_active=True)
    bases = BasisOfDiagnosis.objects.filter(is_active=True)
    staging_systems = StagingSystem.objects.filter(is_active=True)

    # 1. Gather all diagnosis choices from Pathology (Histopathology & Cytology) and Molecular reports
    pathology_choices = []
    seen_texts = set()
    latest_detected_grade_id = None

    for p in patient.pathology_reports.filter(soft_deleted=False).select_related('histology', 'grade').order_by('-path_date'):
        # Direct Histology from Pathology Form dropdown
        if p.histology:
            hname = p.histology.histology_name
            if hname not in seen_texts:
                seen_texts.add(hname)
                gid = p.grade_id or detect_grade_from_text(p.impression or '')
                if not latest_detected_grade_id and gid:
                    latest_detected_grade_id = gid
                gname = p.grade.grade_name if p.grade else (Grade.objects.filter(grade_id=gid).first().grade_name if gid else '')
                pathology_choices.append({
                    'source': 'Biopsy Histology',
                    'date': p.path_date,
                    'text': hname,
                    'standard_histology_id': p.histology_id,
                    'detected_grade_id': gid or '',
                    'detected_grade_name': gname,
                })

        if p.impression and p.impression.strip():
            txt = p.impression.strip()
            if txt not in seen_texts:
                seen_texts.add(txt)
                gid = p.grade_id or detect_grade_from_text(txt) or detect_grade_from_text(p.details or '')
                if not latest_detected_grade_id and gid:
                    latest_detected_grade_id = gid
                gname = p.grade.grade_name if p.grade else (Grade.objects.filter(grade_id=gid).first().grade_name if gid else '')
                pathology_choices.append({
                    'source': 'Histopathology',
                    'date': p.path_date,
                    'text': txt,
                    'detected_grade_id': gid or '',
                    'detected_grade_name': gname,
                })
        if p.details and p.details.strip():
            for line in p.details.splitlines():
                line = line.strip()
                if line and len(line) < 120 and any(k in line.lower() for k in ['carcinoma', 'sarcoma', 'neoplasm', 'tumor', 'differentiat', 'grade']):
                    if line not in seen_texts:
                        seen_texts.add(line)
                        gid = detect_grade_from_text(line)
                        if not latest_detected_grade_id and gid:
                            latest_detected_grade_id = gid
                        gname = Grade.objects.filter(grade_id=gid).first().grade_name if gid else ''
                        pathology_choices.append({
                            'source': 'Pathology Detail',
                            'date': p.path_date,
                            'text': line,
                            'detected_grade_id': gid or '',
                            'detected_grade_name': gname,
                        })

    for m in patient.molecular_tests.filter(soft_deleted=False).order_by('-test_date'):
        if m.impression and m.impression.strip():
            txt = m.impression.strip()
            if txt not in seen_texts:
                seen_texts.add(txt)
                pathology_choices.append({
                    'source': 'Molecular / IHC',
                    'date': m.test_date,
                    'text': txt,
                    'detected_grade_id': '',
                    'detected_grade_name': '',
                })
        for r in m.results.all():
            if r.result_value and r.result_value.strip():
                txt = f"{r.marker.marker_name}: {r.result_value.strip()}"
                if txt not in seen_texts:
                    seen_texts.add(txt)
                    pathology_choices.append({
                        'source': 'Biomarker',
                        'date': m.test_date,
                        'text': txt,
                        'detected_grade_id': '',
                        'detected_grade_name': '',
                    })

    if request.method == 'POST':
        diag_id_post = request.POST.get('diagnosis_id')
        if diag_id_post:
            diagnosis = get_object_or_404(Diagnosis, pk=diag_id_post, patient=patient)
        elif not diagnosis or is_new:
            next_seq = all_diagnoses.count() + 1
            diagnosis = Diagnosis(patient=patient, diagnosis_sequence=next_seq, entered_by=request.user.username)

        diagnosis.date_of_diagnosis = request.POST.get('date_of_diagnosis') or date.today()
        diagnosis.primary_site_id = request.POST.get('primary_site_id') or None
        
        # Full Diagnosis (manually entered)
        diagnosis.diagnosis_description = request.POST.get('diagnosis_description', '').strip()
        
        # Histological type from dropdown
        choice = request.POST.get('histology_choice', '').strip()
        histology_other_manual = request.POST.get('histology_other', '').strip()
        
        if choice.startswith('standard:'):
            try:
                diagnosis.histology_id = int(choice.split(':')[1])
            except (ValueError, IndexError):
                diagnosis.histology_id = None
            diagnosis.histology_other = histology_other_manual
        elif choice.startswith('custom:'):
            custom_val = choice[7:].strip()
            if custom_val == 'OTHER':
                diagnosis.histology_id = None
                diagnosis.histology_other = histology_other_manual
            else:
                diagnosis.histology_other = custom_val
                # Attempt heuristic match with standard histology list
                matched_h = None
                for h in histologies:
                    if h.histology_name.lower() in custom_val.lower():
                        matched_h = h
                        break
                diagnosis.histology_id = matched_h.histology_id if matched_h else None
        else:
            diagnosis.histology_id = request.POST.get('histology_id') or None
            diagnosis.histology_other = histology_other_manual

        # Grade (auto-populated or selected)
        grade_id_val = request.POST.get('grade_id')
        if not grade_id_val and not diagnosis.grade_id and latest_detected_grade_id:
            grade_id_val = latest_detected_grade_id
        diagnosis.grade_id = grade_id_val or None

        diagnosis.basis_id = request.POST.get('basis_id') or None

        # Stage (manually entered)
        diagnosis.staging_system_id = request.POST.get('staging_system_id') or None
        diagnosis.stage_text = request.POST.get('stage_text', '').strip()
        diagnosis.t_status = request.POST.get('t_status', '').strip()
        diagnosis.n_status = request.POST.get('n_status', '').strip()
        diagnosis.m_status = request.POST.get('m_status', '').strip()
        diagnosis.laterality = request.POST.get('laterality', '')

        diagnosis.pathology_text = request.POST.get('pathology_text', '')
        diagnosis.comments = request.POST.get('comments', '')
        diagnosis.last_modified_by = request.user.username

        # Set Primary status
        make_primary = bool(request.POST.get('is_current')) or (all_diagnoses.count() == 0)
        if make_primary:
            patient.diagnoses.exclude(pk=diagnosis.pk).update(is_current=False)
            diagnosis.is_current = True
        else:
            diagnosis.is_current = False

        # Auto-assemble full diagnosis description if left blank
        if not diagnosis.diagnosis_description:
            import re
            site_obj = diagnosis.primary_site
            site_raw = site_obj.site if site_obj else ''
            if site_raw and not site_raw.lower().startswith('ca') and not site_raw.lower().startswith('cancer'):
                site_str = f"Ca {site_raw}"
            else:
                site_str = site_raw

            hist_raw = diagnosis.histology_other or (diagnosis.histology.histology_name if diagnosis.histology else '')
            if hist_raw:
                hist_str = re.sub(r'carcinoma', 'Ca', hist_raw, flags=re.I)
            else:
                hist_str = ''

            grade_str = ''
            if diagnosis.grade and diagnosis.grade.grade_name:
                g_match = re.search(r'G([1-4])', diagnosis.grade.grade_name, re.I)
                if g_match:
                    grade_str = f"Grade {g_match.group(1)}"
                elif 'cannot' not in diagnosis.grade.grade_name.lower():
                    grade_str = diagnosis.grade.grade_name.split(' - ')[0]

            stage_str = f"Stage {diagnosis.stage_text}" if diagnosis.stage_text else ''

            parts = [p for p in [site_str, hist_str, grade_str, stage_str] if p]
            if parts:
                diagnosis.diagnosis_description = ", ".join(parts)

        diagnosis.save()

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="UPDATE" if diagnosis.diagnosis_id else "INSERT",
            table_affected="tblDiagnosis",
            record_ref=f"{patient.mr_no}-Diag#{diagnosis.diagnosis_id}",
            notes=f"Saved diagnosis: {diagnosis.diagnosis_description or diagnosis.primary_site} ({diagnosis.stage_text})"
        )

        messages.success(request, f"Diagnosis for {patient.pt_name} saved successfully.")
        if 'save_next' in request.POST:
            return redirect('nact_router', mr_no=patient.mr_no)
        return redirect('diagnosis_detail', mr_no=patient.mr_no)

    # Auto-detect default grade for form if new diagnosis
    default_grade_id = None
    if not diagnosis or not diagnosis.grade_id:
        default_grade_id = latest_detected_grade_id

    return render(request, 'clinical/diagnosis_form.html', {
        'patient': patient,
        'diagnosis': diagnosis,
        'all_diagnoses': all_diagnoses,
        'is_new': is_new,
        'sites': sites,
        'histologies': histologies,
        'grades': grades,
        'default_grade_id': default_grade_id,
        'bases': bases,
        'staging_systems': staging_systems,
        'pathology_choices': pathology_choices,
    })


@login_required
def diagnosis_delete_view(request, mr_no, diagnosis_id):
    """Deletes (soft delete) a diagnosis record."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    diag = get_object_or_404(Diagnosis, pk=diagnosis_id, patient=patient)
    was_primary = diag.is_current
    diag.soft_deleted = True
    diag.save()

    if was_primary:
        remaining = patient.diagnoses.filter(soft_deleted=False).first()
        if remaining:
            remaining.is_current = True
            remaining.save()

    AuditLog.objects.create(
        username=request.user.username,
        full_name=request.user.first_name,
        action="DELETE",
        table_affected="tblDiagnosis",
        record_ref=f"{patient.mr_no}-Diag#{diag.diagnosis_id}",
        notes=f"Deleted diagnosis #{diag.diagnosis_id}: {diag.diagnosis_description or diag.primary_site}"
    )
    messages.success(request, f"Diagnosis record #{diagnosis_id} removed.")
    return redirect('diagnosis_detail', mr_no=patient.mr_no)


@login_required
def diagnosis_set_primary_view(request, mr_no, diagnosis_id):
    """Sets the chosen diagnosis as the patient's primary diagnosis."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    patient.diagnoses.exclude(pk=diagnosis_id).update(is_current=False)
    diag = get_object_or_404(Diagnosis, pk=diagnosis_id, patient=patient)
    diag.is_current = True
    diag.save()
    messages.success(request, f"Diagnosis '{diag.diagnosis_description or diag.primary_site}' set as Primary.")
    return redirect('diagnosis_detail', mr_no=patient.mr_no)


@login_required
def examination_detail_view(request, mr_no, enc_type='baseline'):
    """Replicates frmEncounter / frmExamination - Physical and pelvic exam."""
    patient = get_object_or_404(Patient, mr_no=mr_no)

    # Determine encounter type
    enc_type_lower = enc_type.lower()
    if 'post-nact' in enc_type_lower or 'nact' in enc_type_lower:
        match_query = 'Post-NACT'
    elif 'brachy' in enc_type_lower:
        match_query = 'Pre-Brachy'
    elif 'follow' in enc_type_lower:
        match_query = 'Follow-up'
    else:
        match_query = 'Baseline'

    encounter_type_obj = EncounterType.objects.filter(encounter_type_name__icontains=match_query).first()
    if not encounter_type_obj:
        encounter_type_obj = EncounterType.objects.first()

    encounter = patient.encounters.filter(encounter_type=encounter_type_obj, soft_deleted=False).first()
    ecog_scores = ECOGScore.objects.filter(is_active=True)

    if request.method == 'POST':
        if not encounter:
            encounter = Encounter(
                patient=patient,
                encounter_type=encounter_type_obj,
                entered_by=request.user.username
            )

        encounter.encounter_date = request.POST.get('encounter_date') or date.today()
        encounter.height = float(request.POST.get('height')) if request.POST.get('height') else None
        encounter.weight = float(request.POST.get('weight')) if request.POST.get('weight') else None
        encounter.ecog_id = request.POST.get('ecog_id') or None

        encounter.presenting_complaints = request.POST.get('presenting_complaints', '')
        encounter.examination_findings = request.POST.get('examination_findings', '')

        # Pelvic Examination
        encounter.parametrial_invasion = bool(request.POST.get('parametrial_invasion'))
        encounter.para_left = bool(request.POST.get('para_left'))
        encounter.para_right = bool(request.POST.get('para_right'))
        encounter.para_extent_left_cm = float(request.POST.get('para_extent_left_cm')) if request.POST.get('para_extent_left_cm') else None
        encounter.para_extent_right_cm = float(request.POST.get('para_extent_right_cm')) if request.POST.get('para_extent_right_cm') else None

        encounter.rectal_invasion = bool(request.POST.get('rectal_invasion'))
        encounter.bladder_invasion = bool(request.POST.get('bladder_invasion'))

        encounter.tumour_size_cm = float(request.POST.get('tumour_size_cm')) if request.POST.get('tumour_size_cm') else None
        encounter.tumour_size_2_cm = float(request.POST.get('tumour_size_2_cm')) if request.POST.get('tumour_size_2_cm') else None
        encounter.tumour_size_3_cm = float(request.POST.get('tumour_size_3_cm')) if request.POST.get('tumour_size_3_cm') else None

        encounter.tandem_sounded = bool(request.POST.get('tandem_sounded'))
        encounter.tandem_length_cm = float(request.POST.get('tandem_length_cm')) if request.POST.get('tandem_length_cm') else None

        encounter.last_modified_by = request.user.username
        encounter.save()

        # Auto-populate SVG if requested or if no SVG findings currently exist
        from clinical.svg_generator import auto_populate_svg_from_encounter
        if bool(request.POST.get('auto_populate_svg')) or not encounter.svg_findings.filter(soft_deleted=False).exists():
            auto_populate_svg_from_encounter(encounter, user_username=request.user.username, force_overwrite=bool(request.POST.get('auto_populate_svg')))

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="UPDATE" if encounter.clinical_id else "INSERT",
            table_affected="tblEncounter",
            record_ref=f"{patient.mr_no}-Enc#{encounter.clinical_id}",
            notes=f"Saved examination ({encounter_type_obj.encounter_type_name})"
        )

        messages.success(request, f"{encounter_type_obj.encounter_type_name} examination for {patient.pt_name} saved.")
        if 'open_diagram' in request.POST:
            return redirect('ibs_diagram', encounter_id=encounter.clinical_id)
        if 'save_next' in request.POST:
            return redirect('investigations_hub', mr_no=patient.mr_no)
        if 'save_stay' in request.POST:
            if 'post-nact' in enc_type_lower or (encounter_type_obj and 'nact' in encounter_type_obj.encounter_type_name.lower()):
                enc_slug = 'post-nact'
            elif 'brachy' in enc_type_lower or (encounter_type_obj and 'brachy' in encounter_type_obj.encounter_type_name.lower()):
                enc_slug = 'pre-brachy'
            else:
                enc_slug = 'baseline'
            return redirect('examination_detail', mr_no=patient.mr_no, enc_type=enc_slug)
        return redirect('dashboard')

    # Fetch marked SVG findings for display
    svg_findings = encounter.svg_findings.filter(soft_deleted=False) if encounter else []

    if 'post-nact' in enc_type_lower or (encounter_type_obj and 'nact' in encounter_type_obj.encounter_type_name.lower()):
        enc_slug = 'post-nact'
    elif 'brachy' in enc_type_lower or (encounter_type_obj and 'brachy' in encounter_type_obj.encounter_type_name.lower()):
        enc_slug = 'pre-brachy'
    else:
        enc_slug = 'baseline'

    return render(request, 'clinical/examination_form.html', {
        'patient': patient,
        'encounter': encounter,
        'encounter_type': encounter_type_obj,
        'ecog_scores': ecog_scores,
        'svg_findings': svg_findings,
        'enc_slug': enc_slug,
    })


@login_required
def ibs_diagram_view(request, encounter_id):
    """Replicates IBS_Wrapper.html inside Access - Interactive pelvic diagram."""
    encounter = get_object_or_404(Encounter, clinical_id=encounter_id)
    patient = encounter.patient

    # Load existing findings
    findings = encounter.svg_findings.filter(soft_deleted=False).select_related('region')
    initial_marks = ",".join([f.region.region_code for f in findings if f.region])

    enc_type_name = encounter.encounter_type.encounter_type_name.lower() if encounter.encounter_type else ""
    if 'post-nact' in enc_type_name or 'nact' in enc_type_name:
        enc_slug = 'post-nact'
    elif 'brachy' in enc_type_name:
        enc_slug = 'pre-brachy'
    else:
        enc_slug = 'baseline'

    return render(request, 'clinical/ibs_diagram.html', {
        'encounter': encounter,
        'patient': patient,
        'initial_marks': initial_marks,
        'enc_slug': enc_slug,
    })


@login_required
def save_diagram_findings_view(request, encounter_id):
    """Saves marked anatomical regions into tblClinicalSVGFindings."""
    encounter = get_object_or_404(Encounter, clinical_id=encounter_id)
    patient = encounter.patient

    if request.method == 'POST':
        marked_regions_str = request.POST.get('marked_regions', '').strip()
        marked_codes = [c.strip() for c in marked_regions_str.split(',') if c.strip()]

        # Deactivate previous findings not in the new list
        current_findings = {f.region.region_code: f for f in encounter.svg_findings.select_related('region')}
        
        # Soft delete or remove deselected
        for code, f in current_findings.items():
            if code not in marked_codes:
                f.soft_deleted = True
                f.save()

        # Add or reactivate selected
        for code in marked_codes:
            region = SVGRegion.objects.filter(region_code=code).first()
            if not region:
                continue

            finding, created = ClinicalSVGFinding.objects.get_or_create(
                encounter=encounter,
                region=region,
                defaults={
                    'entered_by': request.user.username,
                    'soft_deleted': False
                }
            )
            if not created and finding.soft_deleted:
                finding.soft_deleted = False
                finding.last_modified_by = request.user.username
                finding.save()

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="UPDATE",
            table_affected="tblClinicalSVGFindings",
            record_ref=f"Encounter#{encounter.clinical_id}",
            notes=f"Updated anatomical diagram findings: {len(marked_codes)} regions marked"
        )

        messages.success(request, f"Saved {len(marked_codes)} marked anatomical region(s) for {patient.pt_name}.")
        enc_type_name = encounter.encounter_type.encounter_type_name.lower() if encounter.encounter_type else ""
        if 'post-nact' in enc_type_name or 'nact' in enc_type_name:
            enc_slug = 'post-nact'
        elif 'pre' in enc_type_name or 'brachy' in enc_type_name:
            enc_slug = 'pre-brachy'
        else:
            enc_slug = 'baseline'
        return redirect('examination_detail', mr_no=patient.mr_no, enc_type=enc_slug)

    return redirect('ibs_diagram', encounter_id=encounter.clinical_id)


@login_required
def auto_populate_svg_view(request, encounter_id):
    """Explicitly auto-populates the SVG anatomical diagram from the encounter's examination findings."""
    encounter = get_object_or_404(Encounter, clinical_id=encounter_id)
    from clinical.svg_generator import auto_populate_svg_from_encounter
    codes = auto_populate_svg_from_encounter(encounter, user_username=request.user.username, force_overwrite=True)
    messages.success(request, f"Successfully auto-populated {len(codes)} anatomical pelvic zone(s) on the IBS diagram from examination findings.")
    if request.GET.get('redirect') == 'diagram':
        return redirect('ibs_diagram', encounter_id=encounter.clinical_id)
    enc_type_name = encounter.encounter_type.encounter_type_name.lower() if encounter.encounter_type else ""
    if 'post-nact' in enc_type_name or 'nact' in enc_type_name:
        enc_slug = 'post-nact'
    elif 'brachy' in enc_type_name:
        enc_slug = 'pre-brachy'
    else:
        enc_slug = 'baseline'
    return redirect('examination_detail', mr_no=encounter.patient.mr_no, enc_type=enc_slug)


@login_required
def auto_populate_previous_diagram_view(request, encounter_id):
    """
    Auto-populates the SVG clinical diagram with examination findings from the previous encounter.
    For Pre-Brachy: Looks for Post-NACT first, then Baseline.
    For Post-NACT: Looks for Baseline.
    If no previous encounter or no previous findings recorded (e.g. outside EBRT / brachy-only):
        Displays message 'No previous findings recorded'.
    """
    encounter = get_object_or_404(Encounter, clinical_id=encounter_id)
    patient = encounter.patient
    current_type_name = encounter.encounter_type.encounter_type_name.lower() if encounter.encounter_type else ""

    prior_encounter = None

    if 'brachy' in current_type_name:
        # Check Post-NACT first
        prior_nact = patient.encounters.filter(
            soft_deleted=False,
            encounter_type__encounter_type_name__icontains='Post-NACT'
        ).exclude(clinical_id=encounter.clinical_id).order_by('-encounter_date').first()

        if prior_nact and prior_nact.svg_findings.filter(soft_deleted=False).exists():
            prior_encounter = prior_nact
        else:
            # Check Baseline
            prior_base = patient.encounters.filter(
                soft_deleted=False,
                encounter_type__encounter_type_name__icontains='Baseline'
            ).exclude(clinical_id=encounter.clinical_id).order_by('-encounter_date').first()
            if prior_base and prior_base.svg_findings.filter(soft_deleted=False).exists():
                prior_encounter = prior_base
            elif prior_nact:
                prior_encounter = prior_nact
            elif prior_base:
                prior_encounter = prior_base
    elif 'post-nact' in current_type_name or 'nact' in current_type_name:
        # Check Baseline
        prior_base = patient.encounters.filter(
            soft_deleted=False,
            encounter_type__encounter_type_name__icontains='Baseline'
        ).exclude(clinical_id=encounter.clinical_id).order_by('-encounter_date').first()
        prior_encounter = prior_base
    else:
        # Other or Baseline: look for any earlier encounter
        prior_encounter = patient.encounters.filter(
            soft_deleted=False,
            encounter_date__lt=encounter.encounter_date
        ).exclude(clinical_id=encounter.clinical_id).order_by('-encounter_date').first()

    # Determine enc_slug
    if 'post-nact' in current_type_name or 'nact' in current_type_name:
        enc_slug = 'post-nact'
    elif 'brachy' in current_type_name:
        enc_slug = 'pre-brachy'
    else:
        enc_slug = 'baseline'

    # Check if prior encounter has any SVG findings
    prior_findings = prior_encounter.svg_findings.filter(soft_deleted=False) if prior_encounter else None

    if not prior_findings or not prior_findings.exists():
        messages.info(request, "No previous findings recorded")
        if request.GET.get('redirect') == 'exam':
            return redirect('examination_detail', mr_no=patient.mr_no, enc_type=enc_slug)
        return redirect('ibs_diagram', encounter_id=encounter.clinical_id)

    # Copy findings from prior_encounter to current encounter
    copied_count = 0
    for pf in prior_findings:
        finding, created = ClinicalSVGFinding.objects.get_or_create(
            encounter=encounter,
            region=pf.region,
            defaults={
                'involvement_type': pf.involvement_type,
                'lesion_type': pf.lesion_type,
                'depth_of_invasion': pf.depth_of_invasion,
                'bleeds_on_touch': pf.bleeds_on_touch,
                'necrotic': pf.necrotic,
                'region_notes': pf.region_notes,
                'entered_by': request.user.username,
                'soft_deleted': False
            }
        )
        if not created and finding.soft_deleted:
            finding.soft_deleted = False
            finding.involvement_type = pf.involvement_type
            finding.lesion_type = pf.lesion_type
            finding.depth_of_invasion = pf.depth_of_invasion
            finding.bleeds_on_touch = pf.bleeds_on_touch
            finding.necrotic = pf.necrotic
            finding.region_notes = pf.region_notes
            finding.last_modified_by = request.user.username
            finding.save()
        copied_count += 1

    encounter.autopopulated_from_clinical_id = prior_encounter.clinical_id
    encounter.save()

    source_label = prior_encounter.encounter_type.encounter_type_name if prior_encounter.encounter_type else "previous examination"
    messages.success(request, f"Previous examination findings successfully auto-populated from {source_label} ({copied_count} anatomical zone(s) mapped).")

    if request.GET.get('redirect') == 'exam':
        return redirect('examination_detail', mr_no=patient.mr_no, enc_type=enc_slug)
    return redirect('ibs_diagram', encounter_id=encounter.clinical_id)


@login_required
def examination_pdf_view(request, mr_no, enc_type='baseline'):
    """Generates and serves A4 PDF report of Clinical Examination, Populated IBS Diagrams and Chronological Imaging."""
    from django.http import HttpResponse
    patient = get_object_or_404(Patient, mr_no=mr_no)

    from clinical.pdf_examination import build_examination_investigation_pdf
    buf = build_examination_investigation_pdf(patient)
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    filename = f"Examination_Imaging_Report_{patient.mr_no}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response
