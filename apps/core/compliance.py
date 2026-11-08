from datetime import date
from core.models import ComplianceReason, TREATMENT_STATUS_CHOICES

STATUSES_REQUIRING_REASON = ['NOT_STARTED', 'ON_HOLD', 'DISCONTINUED']

STATUS_DEFINITIONS = {
    'PLANNED': 'Treatment planned but not yet initiated',
    'ONGOING': 'Treatment started and currently continuing',
    'ON_HOLD': 'Treatment temporarily interrupted, with possible resumption',
    'COMPLETED': 'Prescribed treatment course completed',
    'NOT_STARTED': 'Planned treatment definitively not initiated',
    'DISCONTINUED': 'Treatment initiated but permanently stopped before completion',
}


def get_compliance_context(course=None):
    """Returns context data needed to render treatment completion and compliance UI."""
    reasons = ComplianceReason.objects.filter(is_active=True).order_by('display_order', 'reason_name')
    return {
        'compliance_reasons': reasons,
        'treatment_status_choices': TREATMENT_STATUS_CHOICES,
        'status_definitions': STATUS_DEFINITIONS,
        'statuses_requiring_reason': STATUSES_REQUIRING_REASON,
    }


def validate_and_apply_compliance(request, course, scheduled_start_date=None):
    """
    Validates and updates compliance fields on course instance:
    - treatment_status: mandatory, choices PLANNED, ONGOING, ON_HOLD, COMPLETED, NOT_STARTED, DISCONTINUED.
    - compliance_reason: mandatory if status in [NOT_STARTED, ON_HOLD, DISCONTINUED]. Must be applicable to that status.
    - compliance_reason_other: mandatory if reason is OTHER.
    - compliance_remarks: optional text.
    - enforces rule: scheduled future date cannot be NOT_STARTED.

    Returns (is_valid: bool, error_message: str or None).
    """
    valid_codes = dict(TREATMENT_STATUS_CHOICES)
    raw_status = (request.POST.get('treatment_status') or 'PLANNED').strip().upper()
    if raw_status not in valid_codes:
        raw_status = 'PLANNED'

    # Check future scheduled date rule:
    # A patient whose treatment is scheduled for a future date must remain PLANNED, not NOT_STARTED.
    if raw_status == 'NOT_STARTED':
        # If scheduled_start_date is not passed, check common course attribute names
        if not scheduled_start_date:
            scheduled_start_date = (
                getattr(course, 'ebrt_start_date', None) or
                getattr(course, 'brachy_start_date', None) or
                getattr(course, 'nact_start_date', None) or
                getattr(course, 'adjuvant_start_date', None)
            )
        if scheduled_start_date and scheduled_start_date > date.today():
            return False, "Treatment scheduled for a future date must remain 'Planned', not 'Not Started'."

    if raw_status in STATUSES_REQUIRING_REASON:
        reason_id = request.POST.get('compliance_reason_id') or request.POST.get('compliance_reason')
        if not reason_id:
            status_label = valid_codes.get(raw_status, raw_status)
            return False, f"Reason is mandatory when Treatment Status is '{status_label}'."

        try:
            reason = ComplianceReason.objects.filter(pk=reason_id, is_active=True).first()
        except (ValueError, TypeError):
            reason = None

        if not reason:
            return False, "Selected Reason was not found or is inactive."

        # Verify applicability configured by administrator
        if raw_status == 'NOT_STARTED' and not reason.applicable_to_not_started:
            return False, f"Reason '{reason.reason_name}' is not configured as applicable when treatment is Not Started."
        if raw_status == 'ON_HOLD' and not reason.applicable_to_on_hold:
            return False, f"Reason '{reason.reason_name}' is not configured as applicable when treatment is On Hold."
        if raw_status == 'DISCONTINUED' and not reason.applicable_to_discontinued:
            return False, f"Reason '{reason.reason_name}' is not configured as applicable when treatment is Discontinued."

        if reason.reason_code == 'OTHER':
            other_text = (request.POST.get('compliance_reason_other') or '').strip()
            if not other_text:
                return False, "Please specify the reason in 'Specify Reason' when 'Other' is selected."
            course.compliance_reason_other = other_text
        else:
            course.compliance_reason_other = None

        course.compliance_reason = reason
    else:
        # PLANNED, ONGOING, COMPLETED do not use reason
        course.compliance_reason = None
        course.compliance_reason_other = None

    course.treatment_status = raw_status
    course.compliance_remarks = (request.POST.get('compliance_remarks') or '').strip() or None

    return True, None
