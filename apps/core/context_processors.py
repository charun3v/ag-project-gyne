from core.permissions import (
    is_admin_user,
    can_delete_patient,
    can_manage_users,
    can_export_data,
    can_manage_roles,
)

def app_branding(request):
    """Provides application title, user role, and permission flags to all templates."""
    role_obj = None
    is_admin = False
    can_del = False
    can_users = False
    can_exp = False
    can_roles = False

    if request.user.is_authenticated:
        try:
            role_obj = request.user.profile.role
        except Exception:
            pass
        is_admin = is_admin_user(request.user)
        can_del = can_delete_patient(request.user)
        can_users = can_manage_users(request.user)
        can_exp = can_export_data(request.user)
        can_roles = can_manage_roles(request.user)

    primary_sites = []
    try:
        from clinical.models import PrimarySite
        primary_sites = list(PrimarySite.objects.filter(is_active=True).order_by('display_order', 'site'))
    except Exception:
        pass

    return {
        'APP_DEPARTMENT': 'Radiation Oncology',
        'APP_INSTITUTION': 'Kidwai Memorial Institute of Oncology',
        'APP_TITLE': 'Radiation Oncology - Kidwai Memorial Institute of Oncology',
        'APP_VERSION': 'v1.1 (Django Migration)',
        'CURRENT_ROLE': role_obj,
        'IS_ADMIN': is_admin,
        'CAN_DELETE_PATIENT': can_del,
        'CAN_MANAGE_USERS': can_users,
        'CAN_EXPORT_DATA': can_exp,
        'CAN_MANAGE_ROLES': can_roles,
        'PRIMARY_SITES_LIST': primary_sites,
    }
