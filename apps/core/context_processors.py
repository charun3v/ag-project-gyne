def app_branding(request):
    """Provides application title and user role context to all templates."""
    role_obj = None
    if request.user.is_authenticated:
        try:
            role_obj = request.user.profile.role
        except Exception:
            pass

    return {
        'APP_DEPARTMENT': 'Radiation Oncology',
        'APP_INSTITUTION': 'Kidwai Memorial Institute of Oncology',
        'APP_TITLE': 'Radiation Oncology - Kidwai Memorial Institute of Oncology',
        'APP_VERSION': 'v1.1 (Django Migration)',
        'CURRENT_ROLE': role_obj,
    }
