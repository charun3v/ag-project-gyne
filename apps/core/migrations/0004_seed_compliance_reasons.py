from django.db import migrations
from datetime import date

REASONS = [
    {
        'reason_code': 'PATIENT_REFUSAL',
        'reason_name': 'Patient refusal / unwillingness',
        'applicable_to_not_started': True,
        'applicable_to_on_hold': True,
        'applicable_to_discontinued': True,
        'display_order': 1,
    },
    {
        'reason_code': 'DEATH',
        'reason_name': 'Death',
        'applicable_to_not_started': True,
        'applicable_to_on_hold': True,
        'applicable_to_discontinued': True,
        'display_order': 2,
    },
    {
        'reason_code': 'MEDICALLY_UNFIT',
        'reason_name': 'Medically unfit / deterioration in general condition',
        'applicable_to_not_started': True,
        'applicable_to_on_hold': True,
        'applicable_to_discontinued': True,
        'display_order': 3,
    },
    {
        'reason_code': 'TOXICITY',
        'reason_name': 'Treatment-related toxicity',
        'applicable_to_not_started': False,
        'applicable_to_on_hold': True,
        'applicable_to_discontinued': True,
        'display_order': 4,
    },
    {
        'reason_code': 'DEFAULT_LOST_TO_FOLLOWUP',
        'reason_name': 'Default / lost to follow-up',
        'applicable_to_not_started': True,
        'applicable_to_on_hold': True,
        'applicable_to_discontinued': True,
        'display_order': 5,
    },
    {
        'reason_code': 'DISEASE_PROGRESSION',
        'reason_name': 'Disease progression',
        'applicable_to_not_started': True,
        'applicable_to_on_hold': True,
        'applicable_to_discontinued': True,
        'display_order': 6,
    },
    {
        'reason_code': 'FINANCIAL',
        'reason_name': 'Financial constraints',
        'applicable_to_not_started': True,
        'applicable_to_on_hold': True,
        'applicable_to_discontinued': True,
        'display_order': 7,
    },
    {
        'reason_code': 'LOGISTICAL',
        'reason_name': 'Transport / logistical difficulties',
        'applicable_to_not_started': True,
        'applicable_to_on_hold': True,
        'applicable_to_discontinued': True,
        'display_order': 8,
    },
    {
        'reason_code': 'TRANSFERRED',
        'reason_name': 'Transferred to another centre',
        'applicable_to_not_started': True,
        'applicable_to_on_hold': True,
        'applicable_to_discontinued': True,
        'display_order': 9,
    },
    {
        'reason_code': 'PLAN_CHANGED',
        'reason_name': 'Treatment plan changed',
        'applicable_to_not_started': True,
        'applicable_to_on_hold': True,
        'applicable_to_discontinued': True,
        'display_order': 10,
    },
    {
        'reason_code': 'OTHER',
        'reason_name': 'Other',
        'applicable_to_not_started': True,
        'applicable_to_on_hold': True,
        'applicable_to_discontinued': True,
        'display_order': 11,
    },
    {
        'reason_code': 'UNKNOWN',
        'reason_name': 'Unknown',
        'applicable_to_not_started': True,
        'applicable_to_on_hold': True,
        'applicable_to_discontinued': True,
        'display_order': 12,
    },
]


def seed_reasons(apps, schema_editor):
    ComplianceReason = apps.get_model('core', 'ComplianceReason')
    for item in REASONS:
        ComplianceReason.objects.update_or_create(
            reason_code=item['reason_code'],
            defaults={
                'reason_name': item['reason_name'],
                'applicable_to_not_started': item['applicable_to_not_started'],
                'applicable_to_on_hold': item['applicable_to_on_hold'],
                'applicable_to_discontinued': item['applicable_to_discontinued'],
                'display_order': item['display_order'],
                'is_active': True,
            }
        )

    # Sync existing course rows
    today = date.today()

    try:
        EBRTCourse = apps.get_model('radiotherapy', 'EBRTCourse')
        for eb in EBRTCourse.objects.all():
            st_name = eb.course_status.status_name.lower() if eb.course_status and hasattr(eb.course_status, 'status_name') else ''
            if eb.treatment_completed or 'complet' in st_name:
                eb.treatment_status = 'COMPLETED'
            elif 'discontin' in st_name:
                eb.treatment_status = 'DISCONTINUED'
            elif eb.ebrt_start_date and eb.ebrt_start_date <= today:
                eb.treatment_status = 'ONGOING'
            else:
                eb.treatment_status = 'PLANNED'
            eb.save(update_fields=['treatment_status'])
    except LookupError:
        pass

    try:
        BrachyCourse = apps.get_model('radiotherapy', 'BrachyCourse')
        for bc in BrachyCourse.objects.all():
            st_name = bc.course_status.status_name.lower() if bc.course_status and hasattr(bc.course_status, 'status_name') else ''
            comp_st = (bc.completion_status or '').lower()
            if 'complet' in comp_st or 'complet' in st_name:
                bc.treatment_status = 'COMPLETED'
            elif 'discontin' in comp_st or 'discontin' in st_name:
                bc.treatment_status = 'DISCONTINUED'
            elif bc.brachy_start_date and bc.brachy_start_date <= today:
                bc.treatment_status = 'ONGOING'
            else:
                bc.treatment_status = 'PLANNED'
            bc.save(update_fields=['treatment_status'])
    except LookupError:
        pass

    try:
        NACTCourse = apps.get_model('systemic', 'NACTCourse')
        for nc in NACTCourse.objects.all():
            st_name = nc.nact_status.status_name.lower() if nc.nact_status and hasattr(nc.nact_status, 'status_name') else ''
            if 'complet' in st_name:
                nc.treatment_status = 'COMPLETED'
            elif 'discontin' in st_name:
                nc.treatment_status = 'DISCONTINUED'
            elif nc.nact_start_date and nc.nact_start_date <= today:
                nc.treatment_status = 'ONGOING'
            else:
                nc.treatment_status = 'PLANNED'
            nc.save(update_fields=['treatment_status'])
    except LookupError:
        pass

    try:
        AdjuvantChemoCourse = apps.get_model('systemic', 'AdjuvantChemoCourse')
        for ac in AdjuvantChemoCourse.objects.all():
            st_name = ac.chemo_status.status_name.lower() if ac.chemo_status and hasattr(ac.chemo_status, 'status_name') else ''
            if 'complet' in st_name:
                ac.treatment_status = 'COMPLETED'
            elif 'discontin' in st_name:
                ac.treatment_status = 'DISCONTINUED'
            elif ac.adjuvant_start_date and ac.adjuvant_start_date <= today:
                ac.treatment_status = 'ONGOING'
            else:
                ac.treatment_status = 'PLANNED'
            ac.save(update_fields=['treatment_status'])
    except LookupError:
        pass


def rollback_reasons(apps, schema_editor):
    ComplianceReason = apps.get_model('core', 'ComplianceReason')
    ComplianceReason.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_compliancereason'),
        ('radiotherapy', '0006_brachycourse_compliance_reason_and_more'),
        ('systemic', '0006_adjuvantchemocourse_compliance_reason_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_reasons, rollback_reasons),
    ]
