from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import date

from patients.models import Patient
from core.models import AuditLog
from followup.models import (
    FollowUpStatus, FollowUpContactType, ProxyStatus, DiseaseStatus,
    RecurrenceSite, CauseOfDeath
)
from systemic.models import ResponseStatus

@login_required
def followup_list_view(request, mr_no):
    """Replicates frmFollowUpList - Longitudinal surveillance tracking and survival timeline."""
    patient = get_object_or_404(Patient, mr_no=mr_no)
    followups = patient.follow_up_records.filter(soft_deleted=False).select_related('disease_status', 'contact_type', 'recurrence_site')

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

    if request.method == 'POST':
        if not fu:
            fu = FollowUpStatus(patient=patient, entered_by=request.user.username)

        fu.follow_up_date = request.POST.get('follow_up_date') or date.today()
        fu.contact_type_id = request.POST.get('contact_type_id') or None
        fu.proxy_status_id = request.POST.get('proxy_status_id') or None

        fu.disease_status_id = request.POST.get('disease_status_id') or None
        fu.response_status_id = request.POST.get('response_status_id') or None

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

        fu.recurrence_site_id = request.POST.get('recurrence_site_id') or None
        fu.recurrence_treatment_plan = request.POST.get('recurrence_treatment_plan', '')

        # Survival & Death
        fu.death_reported = bool(request.POST.get('death_reported'))
        fu.date_of_death = request.POST.get('date_of_death') or None
        fu.cause_of_death_id = request.POST.get('cause_of_death_id') or None

        fu.performance_notes = request.POST.get('performance_notes', '')
        fu.next_fu_date = request.POST.get('next_fu_date') or None
        fu.next_fu_notes = request.POST.get('next_fu_notes', '')
        fu.last_modified_by = request.user.username
        fu.save()

        AuditLog.objects.create(
            username=request.user.username,
            full_name=request.user.first_name,
            action="UPDATE" if followup_id else "INSERT",
            table_affected="tblFollowUpStatus",
            record_ref=f"{patient.mr_no}-FU#{fu.follow_up_status_id}",
            notes=f"Saved follow-up visit: {fu.disease_status}"
        )

        messages.success(request, f"Follow-up visit record ({fu.follow_up_date}) saved.")
        return redirect('followup_list', mr_no=patient.mr_no)

    return render(request, 'followup/followup_form.html', {
        'patient': patient,
        'fu': fu,
        'contact_types': contact_types,
        'proxy_statuses': proxy_statuses,
        'disease_statuses': disease_statuses,
        'response_statuses': response_statuses,
        'recurrence_sites': recurrence_sites,
        'causes_of_death': causes_of_death,
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
