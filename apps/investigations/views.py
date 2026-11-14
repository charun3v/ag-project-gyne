from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import date

from patients.models import Patient
from core.models import AuditLog
from clinical.models import Histology, Grade
from investigations.models import (
    BloodInvestigation, PathologyInvestigation, ImagingInvestigation, MRIPelvisDetail, MRINodalStation,
    MolecularInvestigation, MolecularResult, ImagingType, ImagingSite, PathSpecimen, PathBiopsySite,
    FNACSite, PathType, MolecularType, MolecularMarker, NodalStation, MRIOrganInvasionStatus
)

@login_required
def investigations_hub_view(request, mr_no):
    """Central Investigations Hub replicating frmInvestigations with tabbed subforms."""
    patient = get_object_or_404(Patient, mr_no=mr_no)

    blood_tests = patient.blood_tests.filter(soft_deleted=False)
    pathology_reports = patient.pathology_reports.filter(soft_deleted=False)
    imaging_studies = patient.imaging_studies.filter(soft_deleted=False).prefetch_related('pelvis_detail__nodal_stations')
    molecular_tests = patient.molecular_tests.filter(soft_deleted=False).prefetch_related('results__marker')

    active_tab = request.GET.get('tab', 'blood')

    return render(request, 'investigations/investigations_hub.html', {
        'patient': patient,
        'blood_tests': blood_tests,
        'pathology_reports': pathology_reports,
        'imaging_studies': imaging_studies,
        'molecular_tests': molecular_tests,
        'active_tab': active_tab,
    })


@login_required
def blood_form_view(request, mr_no, blood_id=None):
    """Replicates frmBlood - Complete hematology, biochemistry and renal panels."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    blood = get_object_or_404(BloodInvestigation, blood_id=blood_id, patient=patient) if blood_id else None

    if request.method == 'POST':
        test_date_raw = request.POST.get('test_date', '').strip()
        if not test_date_raw:
            messages.error(request, "Blood test date is mandatory.")
            return render(request, 'investigations/blood_form.html', {
                'patient': patient,
                'blood': blood,
                'return_to': request.GET.get('return_to', '') or request.POST.get('return_to', ''),
                'fu_id': request.GET.get('fu_id', '') or request.POST.get('fu_id', ''),
            })

        if not blood:
            blood = BloodInvestigation(patient=patient, entered_by=request.user.username)

        blood.test_date = test_date_raw
        blood.lab_reference_no = request.POST.get('lab_reference_no', '')
        blood.specimen_type = request.POST.get('specimen_type', 'Blood')

        # CBC
        blood.hb = float(request.POST.get('hb')) if request.POST.get('hb') else None
        blood.tc = float(request.POST.get('tc')) if request.POST.get('tc') else None
        blood.anc = float(request.POST.get('anc')) if request.POST.get('anc') else None
        blood.alc = float(request.POST.get('alc')) if request.POST.get('alc') else None
        blood.platelet = float(request.POST.get('platelet')) if request.POST.get('platelet') else None

        # RFT
        blood.serum_urea = float(request.POST.get('serum_urea')) if request.POST.get('serum_urea') else None
        blood.serum_creatinine = float(request.POST.get('serum_creatinine')) if request.POST.get('serum_creatinine') else None

        # LFT
        blood.total_protein = float(request.POST.get('total_protein')) if request.POST.get('total_protein') else None
        blood.serum_albumin = float(request.POST.get('serum_albumin')) if request.POST.get('serum_albumin') else None
        blood.sgot = float(request.POST.get('sgot')) if request.POST.get('sgot') else None
        blood.sgpt = float(request.POST.get('sgpt')) if request.POST.get('sgpt') else None
        blood.alp = float(request.POST.get('alp')) if request.POST.get('alp') else None

        # Electrolytes
        blood.serum_sodium = float(request.POST.get('serum_sodium')) if request.POST.get('serum_sodium') else None
        blood.serum_potassium = float(request.POST.get('serum_potassium')) if request.POST.get('serum_potassium') else None
        blood.serum_calcium = float(request.POST.get('serum_calcium')) if request.POST.get('serum_calcium') else None

        blood.details = request.POST.get('details', '')
        blood.impression = request.POST.get('impression', '')
        blood.save()

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="UPDATE" if blood_id else "INSERT",
            table_affected="tblBlood",
            record_ref=f"{patient.mr_no}-Blood#{blood.blood_id}",
            notes=f"Saved blood investigation ({blood.test_date})"
        )

        messages.success(request, f"Blood test record ({blood.test_date}) saved.")
        return_to = request.GET.get('return_to') or request.POST.get('return_to')
        fu_id = request.GET.get('fu_id') or request.POST.get('fu_id')
        if return_to == 'followup':
            if fu_id:
                try:
                    from followup.models import FollowUpInvestigationLink
                    FollowUpInvestigationLink.objects.get_or_create(
                        follow_up_id=int(fu_id),
                        investigation_type='Blood',
                        investigation_id=blood.blood_id
                    )
                except Exception:
                    pass
                return redirect('followup_edit', mr_no=patient.mr_no, followup_id=fu_id)
            return redirect('followup_list', mr_no=patient.mr_no)

        if 'save_next' in request.POST:
            return redirect('investigations_hub', mr_no=patient.mr_no)
        return redirect(f"/investigations/{patient.mr_no}/hub/?tab=blood")

    return_to = request.GET.get('return_to', '')
    fu_id = request.GET.get('fu_id', '')

    return render(request, 'investigations/blood_form.html', {
        'patient': patient,
        'blood': blood,
        'return_to': return_to,
        'fu_id': fu_id,
    })


@login_required
def pathology_form_view(request, mr_no, path_id=None):
    """Replicates frmPathology - Biopsy and cytology reports."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    path_report = get_object_or_404(PathologyInvestigation, path_id=path_id, patient=patient) if path_id else None

    specimens = PathSpecimen.objects.filter(is_active=True)
    biopsy_sites = PathBiopsySite.objects.filter(is_active=True)
    path_types = PathType.objects.filter(is_active=True)
    fnac_sites = FNACSite.objects.filter(is_active=True)
    histologies = Histology.objects.filter(is_active=True)
    grades = Grade.objects.filter(is_active=True)

    if request.method == 'POST':
        path_date_raw = request.POST.get('path_date', '').strip()
        if not path_date_raw:
            messages.error(request, "Pathology report date is mandatory.")
            return render(request, 'investigations/pathology_form.html', {
                'patient': patient,
                'path_report': path_report,
                'specimens': specimens,
                'biopsy_sites': biopsy_sites,
                'path_types': path_types,
                'fnac_sites': fnac_sites,
                'histologies': histologies,
                'grades': grades,
                'return_to': request.GET.get('return_to', '') or request.POST.get('return_to', ''),
                'fu_id': request.GET.get('fu_id', '') or request.POST.get('fu_id', ''),
            })

        if not path_report:
            path_report = PathologyInvestigation(patient=patient, entered_by=request.user.username)

        path_report.path_date = path_date_raw
        path_report.lab_reference_no = request.POST.get('lab_reference_no', '')
        path_report.specimen_id = request.POST.get('specimen_id') or None
        path_report.biopsy_site_id = request.POST.get('biopsy_site_id') or None
        path_report.path_type_id = request.POST.get('path_type_id') or None
        path_report.fnac_site_id = request.POST.get('fnac_site_id') or None
        path_report.histology_id = request.POST.get('histology_id') or None
        path_report.grade_id = request.POST.get('grade_id') or None

        path_report.details = request.POST.get('details', '')
        impression_val = request.POST.get('impression', '').strip()
        if not impression_val and path_report.histology:
            parts = [path_report.histology.histology_name]
            if path_report.grade:
                parts.append(path_report.grade.grade_name)
            impression_val = ", ".join(parts)
        path_report.impression = impression_val
        path_report.last_modified_by = request.user.username
        path_report.save()

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="UPDATE" if path_id else "INSERT",
            table_affected="tblPath",
            record_ref=f"{patient.mr_no}-Path#{path_report.path_id}",
            notes=f"Saved pathology report ({path_report.path_date})"
        )

        messages.success(request, f"Pathology report ({path_report.path_date}) saved.")
        return_to = request.GET.get('return_to') or request.POST.get('return_to')
        fu_id = request.GET.get('fu_id') or request.POST.get('fu_id')
        if return_to == 'followup':
            if fu_id:
                try:
                    from followup.models import FollowUpInvestigationLink
                    FollowUpInvestigationLink.objects.get_or_create(
                        follow_up_id=int(fu_id),
                        investigation_type='Pathology',
                        investigation_id=path_report.path_id
                    )
                except Exception:
                    pass
                return redirect('followup_edit', mr_no=patient.mr_no, followup_id=fu_id)
            return redirect('followup_list', mr_no=patient.mr_no)

        if 'save_stay' in request.POST:
            return redirect('pathology_edit', mr_no=patient.mr_no, path_id=path_report.path_id)
        return redirect(f"/investigations/{patient.mr_no}/hub/?tab=pathology")

    return_to = request.GET.get('return_to', '')
    fu_id = request.GET.get('fu_id', '')

    return render(request, 'investigations/pathology_form.html', {
        'patient': patient,
        'path_report': path_report,
        'specimens': specimens,
        'biopsy_sites': biopsy_sites,
        'path_types': path_types,
        'fnac_sites': fnac_sites,
        'histologies': histologies,
        'grades': grades,
        'return_to': return_to,
        'fu_id': fu_id,
    })


@login_required
def imaging_form_view(request, mr_no, imaging_id=None):
    """Replicates frmImaging - Radiology imaging with MRI Pelvis detail & nodal stations."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    imaging = get_object_or_404(ImagingInvestigation, imaging_id=imaging_id, patient=patient) if imaging_id else None

    imaging_types = ImagingType.objects.filter(is_active=True)
    imaging_sites = ImagingSite.objects.filter(is_active=True)
    organ_statuses = MRIOrganInvasionStatus.objects.filter(is_active=True)
    nodal_stations_lookup = NodalStation.objects.filter(is_active=True)

    pelvis_detail = getattr(imaging, 'pelvis_detail', None) if imaging else None

    selected_site_ids = []
    if imaging:
        selected_site_ids = list(imaging.imaging_sites.values_list('imaging_site_id', flat=True))
        if not selected_site_ids and imaging.imaging_site_id:
            selected_site_ids = [imaging.imaging_site_id]
    else:
        pelvis_site = imaging_sites.filter(imaging_site_name__icontains='Pelvis').first()
        if pelvis_site:
            selected_site_ids = [pelvis_site.imaging_site_id]

    if request.method == 'POST':
        imaging_date_raw = request.POST.get('imaging_date', '').strip()
        raw_site_ids = request.POST.getlist('imaging_site_ids')
        curr_selected_ids = [int(x) for x in raw_site_ids if str(x).isdigit()]

        if not imaging_date_raw:
            messages.error(request, "Imaging investigation date is mandatory.")
            return render(request, 'investigations/imaging_form.html', {
                'patient': patient,
                'imaging': imaging,
                'pelvis_detail': pelvis_detail,
                'imaging_types': imaging_types,
                'imaging_sites': imaging_sites,
                'selected_site_ids': curr_selected_ids,
                'organ_statuses': organ_statuses,
                'nodal_stations_lookup': nodal_stations_lookup,
                'return_to': request.GET.get('return_to', '') or request.POST.get('return_to', ''),
                'fu_id': request.GET.get('fu_id', '') or request.POST.get('fu_id', ''),
            })

        impression = request.POST.get('impression', '').strip()
        if not impression:
            messages.error(request, "Overall Imaging Impression is mandatory.")
            return render(request, 'investigations/imaging_form.html', {
                'patient': patient,
                'imaging': imaging,
                'pelvis_detail': pelvis_detail,
                'imaging_types': imaging_types,
                'imaging_sites': imaging_sites,
                'selected_site_ids': curr_selected_ids,
                'organ_statuses': organ_statuses,
                'nodal_stations_lookup': nodal_stations_lookup,
                'return_to': request.GET.get('return_to', '') or request.POST.get('return_to', ''),
                'fu_id': request.GET.get('fu_id', '') or request.POST.get('fu_id', ''),
            })

        if not imaging:
            imaging = ImagingInvestigation(patient=patient, entered_by=request.user.username)

        imaging.imaging_date = imaging_date_raw
        imaging.imaging_type_id = request.POST.get('imaging_type_id') or None
        
        # Multi-select Anatomical Sites
        raw_site_ids = request.POST.getlist('imaging_site_ids')
        if not raw_site_ids and request.POST.get('imaging_site_id'):
            raw_site_ids = [request.POST.get('imaging_site_id')]
        site_ids = [int(s) for s in raw_site_ids if str(s).isdigit()]

        imaging.imaging_site_id = site_ids[0] if site_ids else None
        imaging.lab_reference_no = request.POST.get('lab_reference_no', '').strip()
        imaging.other_modality = request.POST.get('other_modality', '').strip()
        imaging.details = request.POST.get('details', '').strip()
        imaging.impression = impression
        imaging.last_modified_by = request.user.username
        imaging.save()

        # Save M2M anatomical sites
        if site_ids:
            imaging.imaging_sites.set(site_ids)
        else:
            imaging.imaging_sites.clear()

        # Check if MRI and Pelvis are selected: Pelvic MRI Anatomical Staging is only saved if MRI Pelvis is selected
        is_mri = bool(imaging.imaging_type and 'mri' in imaging.imaging_type.imaging_type_name.lower())
        is_pelvis = bool(
            imaging.imaging_sites.filter(imaging_site_name__icontains='Pelvis').exists() or 
            (imaging.imaging_site and 'pelvis' in imaging.imaging_site.imaging_site_name.lower())
        )

        if is_mri and is_pelvis:
            if not pelvis_detail:
                pelvis_detail, _ = MRIPelvisDetail.objects.get_or_create(imaging=imaging)

            pelvis_detail.tumour_dimension_1_cm = float(request.POST.get('tumour_dimension_1_cm')) if request.POST.get('tumour_dimension_1_cm') else None
            pelvis_detail.tumour_dimension_2_cm = float(request.POST.get('tumour_dimension_2_cm')) if request.POST.get('tumour_dimension_2_cm') else None
            pelvis_detail.tumour_dimension_3_cm = float(request.POST.get('tumour_dimension_3_cm')) if request.POST.get('tumour_dimension_3_cm') else None
            pelvis_detail.tumour_volume_cc = None

            pelvis_detail.cervix_involved = bool(request.POST.get('cervix_involved'))
            pelvis_detail.cervical_stromal_invasion = bool(request.POST.get('cervical_stromal_invasion'))
            pelvis_detail.cervical_stromal_extent = request.POST.get('cervical_stromal_extent', '')

            pelvis_detail.uterine_corpus_involved = bool(request.POST.get('uterine_corpus_involved'))
            
            # Vaginal Involvement / Extension: mandatory extent when checked
            pelvis_detail.vaginal_involvement = bool(request.POST.get('vaginal_involvement'))
            if pelvis_detail.vaginal_involvement:
                vaginal_extent_val = request.POST.get('vaginal_extent', '').strip()
                if not vaginal_extent_val:
                    messages.error(request, "Vaginal Extent is mandatory when Vaginal Extension is selected.")
                    return render(request, 'investigations/imaging_form.html', {
                        'patient': patient,
                        'imaging': imaging,
                        'pelvis_detail': pelvis_detail,
                        'imaging_types': imaging_types,
                        'imaging_sites': imaging_sites,
                        'selected_site_ids': site_ids,
                        'organ_statuses': organ_statuses,
                        'nodal_stations_lookup': nodal_stations_lookup,
                    })
                pelvis_detail.vaginal_extent = vaginal_extent_val
            else:
                pelvis_detail.vaginal_extent = ''

            # Parametrial Involvement on MRI
            pelvis_detail.parametrium_involved = bool(request.POST.get('parametrium_involved'))
            if pelvis_detail.parametrium_involved:
                pelvis_detail.para_left_involved = bool(request.POST.get('para_left_involved'))
                pelvis_detail.para_right_involved = bool(request.POST.get('para_right_involved'))
                pelvis_detail.para_left_extent_cm = float(request.POST.get('para_left_extent_cm')) if (pelvis_detail.para_left_involved and request.POST.get('para_left_extent_cm')) else None
                pelvis_detail.para_right_extent_cm = float(request.POST.get('para_right_extent_cm')) if (pelvis_detail.para_right_involved and request.POST.get('para_right_extent_cm')) else None
            else:
                pelvis_detail.para_left_involved = False
                pelvis_detail.para_right_involved = False
                pelvis_detail.para_left_extent_cm = None
                pelvis_detail.para_right_extent_cm = None

            pelvis_detail.bladder_status_id = request.POST.get('bladder_status_id') or None
            pelvis_detail.rectum_status_id = request.POST.get('rectum_status_id') or None

            pelvis_detail.hydronephrosis_left = bool(request.POST.get('hydronephrosis_left'))
            pelvis_detail.hydronephrosis_right = bool(request.POST.get('hydronephrosis_right'))

            # Lymph Node Status
            pelvis_detail.nodes_present = request.POST.get('nodes_present') in ['1', 'yes', 'true', True]
            if pelvis_detail.nodes_present:
                pelvis_detail.pelvic_nodes_present = bool(request.POST.get('pelvic_nodes_present'))
                pelvis_detail.pa_nodes_present = bool(request.POST.get('pa_nodes_present'))
                pelvis_detail.inguinal_nodes_present = bool(request.POST.get('inguinal_nodes_present'))
            else:
                pelvis_detail.pelvic_nodes_present = False
                pelvis_detail.pa_nodes_present = False
                pelvis_detail.inguinal_nodes_present = False

            pelvis_detail.distant_findings = request.POST.get('distant_findings', '')
            pelvis_detail.radiologist_impression = request.POST.get('radiologist_impression', '')
            pelvis_detail.save()

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="UPDATE" if imaging_id else "INSERT",
            table_affected="tblImaging",
            record_ref=f"{patient.mr_no}-Img#{imaging.imaging_id}",
            notes=f"Saved imaging study ({imaging.imaging_type})"
        )

        messages.success(request, f"Imaging investigation ({imaging.imaging_type}) saved.")
        return_to = request.GET.get('return_to') or request.POST.get('return_to')
        fu_id = request.GET.get('fu_id') or request.POST.get('fu_id')
        if return_to == 'followup':
            if fu_id:
                try:
                    from followup.models import FollowUpInvestigationLink
                    FollowUpInvestigationLink.objects.get_or_create(
                        follow_up_id=int(fu_id),
                        investigation_type='Imaging',
                        investigation_id=imaging.imaging_id
                    )
                except Exception:
                    pass
                return redirect('followup_edit', mr_no=patient.mr_no, followup_id=fu_id)
            return redirect('followup_list', mr_no=patient.mr_no)

        if 'save_stay' in request.POST:
            return redirect('imaging_edit', mr_no=patient.mr_no, imaging_id=imaging.imaging_id)
        return redirect(f"/investigations/{patient.mr_no}/hub/?tab=imaging")

    return_to = request.GET.get('return_to', '')
    fu_id = request.GET.get('fu_id', '')

    return render(request, 'investigations/imaging_form.html', {
        'patient': patient,
        'imaging': imaging,
        'pelvis_detail': pelvis_detail,
        'imaging_types': imaging_types,
        'imaging_sites': imaging_sites,
        'selected_site_ids': selected_site_ids,
        'organ_statuses': organ_statuses,
        'nodal_stations_lookup': nodal_stations_lookup,
        'return_to': return_to,
        'fu_id': fu_id,
    })


@login_required
def molecular_form_view(request, mr_no, molecular_id=None):
    """Replicates frmMolecular - Molecular pathology, IHC & biomarkers."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    mol = get_object_or_404(MolecularInvestigation, molecular_id=molecular_id, patient=patient) if molecular_id else None

    mol_types = MolecularType.objects.filter(is_active=True)
    specimens = PathSpecimen.objects.filter(is_active=True)
    markers = MolecularMarker.objects.filter(is_active=True)

    if request.method == 'POST':
        test_date_raw = request.POST.get('test_date', '').strip()
        if not test_date_raw:
            messages.error(request, "Molecular test date is mandatory.")
            return render(request, 'investigations/molecular_form.html', {
                'patient': patient,
                'molecular': mol,
                'mol_types': mol_types,
                'specimens': specimens,
                'markers': markers,
                'return_to': request.GET.get('return_to', '') or request.POST.get('return_to', ''),
                'fu_id': request.GET.get('fu_id', '') or request.POST.get('fu_id', ''),
            })

        if not mol:
            mol = MolecularInvestigation(patient=patient, entered_by=request.user.username)

        mol.test_date = test_date_raw
        mol.lab_reference_no = request.POST.get('lab_reference_no', '')
        mol.molecular_type_id = request.POST.get('molecular_type_id') or None
        mol.specimen_id = request.POST.get('specimen_id') or None
        mol.specimen_source = request.POST.get('specimen_source', '')
        mol.testing_lab = request.POST.get('testing_lab', '')
        mol.details = request.POST.get('details', '')
        mol.impression = request.POST.get('impression', '')
        mol.save()

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="UPDATE" if molecular_id else "INSERT",
            table_affected="tblMolecular",
            record_ref=f"{patient.mr_no}-Mol#{mol.molecular_id}",
            notes=f"Saved molecular study ({mol.molecular_type})"
        )

        messages.success(request, f"Molecular and cytogenetics investigation ({mol.test_date}) saved.")
        return_to = request.GET.get('return_to') or request.POST.get('return_to')
        fu_id = request.GET.get('fu_id') or request.POST.get('fu_id')
        if return_to == 'followup':
            if fu_id:
                try:
                    from followup.models import FollowUpInvestigationLink
                    FollowUpInvestigationLink.objects.get_or_create(
                        follow_up_id=int(fu_id),
                        investigation_type='Molecular',
                        investigation_id=mol.molecular_id
                    )
                except Exception:
                    pass
                return redirect('followup_edit', mr_no=patient.mr_no, followup_id=fu_id)
            return redirect('followup_list', mr_no=patient.mr_no)

        if 'save_stay' in request.POST:
            return redirect('molecular_edit', mr_no=patient.mr_no, molecular_id=mol.molecular_id)
        return redirect(f"/investigations/{patient.mr_no}/hub/?tab=molecular")

    return_to = request.GET.get('return_to', '')
    fu_id = request.GET.get('fu_id', '')

    return render(request, 'investigations/molecular_form.html', {
        'patient': patient,
        'molecular': mol,
        'mol_types': mol_types,
        'specimens': specimens,
        'markers': markers,
        'return_to': return_to,
        'fu_id': fu_id,
    })


@login_required
def investigations_pdf_view(request, mr_no):
    """Generates and serves A4 PDF report of Diagnostic Investigations."""
    from django.http import HttpResponse
    patient = get_object_or_404(Patient, mr_no=mr_no)
    from investigations.pdf_investigations import build_investigations_pdf
    buf = build_investigations_pdf(patient)
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    filename = f"Investigations_Report_{patient.mr_no}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response
