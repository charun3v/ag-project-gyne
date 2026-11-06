from core.models import AppSetting, AuditLog

DEFAULT_LOOKUP_SEEDS = {
    'source': ('Ir-192 HDR', 'source_name'),
    'guidance': ('CT-based', 'guidance_name'),
    'dosing': ('HR-CTV D90', 'dosing_point'),
    'anaesthesia': ('Spinal', 'anaesthesia_name'),
    'centre': ('Kidwai', 'centre_name'),
    'intent': ('Radical', 'intent_name'),
    'technique': ('IMRT', 'technique_name'),
    'site': ('Cervix', 'site'),
    'staging_system': ('FIGO', 'system_name'),
}

def get_default_lookup_id(category):
    """
    Returns the primary key of the default option for the given lookup category.
    If not explicitly saved, automatically seeds initial clinical default if available.
    """
    key = f"default_lookup_{category}"
    setting = AppSetting.objects.filter(setting_key=key).first()
    if setting and setting.setting_value:
        val = setting.setting_value.strip()
        try:
            return int(val)
        except (ValueError, TypeError):
            return val

    # Auto-seed initial default if defined in DEFAULT_LOOKUP_SEEDS
    if category in DEFAULT_LOOKUP_SEEDS:
        from core.views import get_lookup_model
        model, cfg = get_lookup_model(category)
        if model and cfg:
            target_str, search_field = DEFAULT_LOOKUP_SEEDS[category]
            filter_kwargs = {f"{search_field}__icontains": target_str, "is_active": True}
            item = model.objects.filter(**filter_kwargs).first() or model.objects.filter(is_active=True).first()
            if item:
                AppSetting.objects.update_or_create(
                    setting_key=key,
                    defaults={'setting_value': str(item.pk)}
                )
                return item.pk
    return None

def set_default_lookup_id(category, item_id, user=None):
    """Saves the default lookup option for category in AppSetting and records audit log."""
    key = f"default_lookup_{category}"
    AppSetting.objects.update_or_create(
        setting_key=key,
        defaults={'setting_value': str(item_id) if item_id is not None else ''}
    )
    if user:
        AuditLog.objects.create(
            username=user.username if hasattr(user, 'username') else str(user),
            full_name=getattr(user, 'first_name', '') or '',
            action="UPDATE",
            table_affected="tblAppSettings",
            record_ref=key,
            notes=f"Selected default option for dropdown '{category}' to ID {item_id}"
        )

def clear_default_lookup_id(category, user=None):
    """Clears the default option for category."""
    key = f"default_lookup_{category}"
    AppSetting.objects.filter(setting_key=key).delete()
    if user:
        AuditLog.objects.create(
            username=user.username if hasattr(user, 'username') else str(user),
            full_name=getattr(user, 'first_name', '') or '',
            action="DELETE",
            table_affected="tblAppSettings",
            record_ref=key,
            notes=f"Cleared default option for dropdown '{category}'"
        )
