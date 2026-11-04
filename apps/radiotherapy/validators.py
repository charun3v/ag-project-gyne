from .models import (
    ApplicatorType,
    ApplicatorMeasurementDefinition,
    ApplicatorFieldRule,
)

ALL_MEASUREMENT_CODES = [
    'tandem_length_cm',
    'ovoid_diameter_mm',
    'ovoid_length_mm',
    'ring_diameter_mm',
    'needle_count',
]


def validate_applicator_measurements(applicator_type, data, is_historical_approved=False, is_completing_or_approving=False):
    """
    Validates physical measurements against active ApplicatorFieldRule configurations.
    Returns a dict of errors: {field_code: error_message}.
    If valid, returns empty dict.
    """
    if isinstance(applicator_type, (int, str)):
        try:
            applicator_type = ApplicatorType.objects.get(id=applicator_type)
        except ApplicatorType.DoesNotExist:
            return {'applicator_id': "Invalid applicator selected."}

    if not applicator_type:
        return {'applicator_id': "Applicator selection is required."}

    # Fetch active definitions and rules for this applicator
    rules = ApplicatorFieldRule.objects.filter(
        applicator_type=applicator_type,
        measurement_definition__active=True
    ).select_related('measurement_definition')

    rule_map = {r.measurement_definition.code: r for r in rules}

    # Map all known measurement definitions for fallback labels
    defs = {d.code: d for d in ApplicatorMeasurementDefinition.objects.filter(active=True)}

    errors = {}

    for code in ALL_MEASUREMENT_CODES:
        val = data.get(code)
        if code == 'needle_count' and val is None:
            val = data.get('number_of_needles')

        rule = rule_map.get(code)
        mdef = defs.get(code)
        label = rule.measurement_definition.label if rule else (mdef.label if mdef else code)

        # Determine if blank
        is_blank = (val is None or val == '' or (isinstance(val, str) and not val.strip()))

        # Check if field is enabled
        is_enabled = rule.enabled if rule else False

        if not is_enabled:
            # Stale or unexpected values supplied for non-enabled fields
            if not is_blank and not is_historical_approved:
                # If needle_count default was 0 or '0', treat as unsupplied/cleared
                if code == 'needle_count' and (val == 0 or val == '0'):
                    continue
                errors[code] = f"{label} does not apply to the selected applicator."
            continue

        # Enabled field: check required
        if rule.required and is_blank:
            errors[code] = f"{label} is required for {applicator_type.name}."
            continue

        # If non-blank, validate data types, range limits, positive values
        if not is_blank:
            if code == 'needle_count':
                # Positive whole number (integer > 0)
                try:
                    f_val = float(val)
                    if not f_val.is_integer() or f_val <= 0:
                        errors[code] = "Number of needles must be a positive whole number."
                        continue
                    num_val = int(f_val)
                except (ValueError, TypeError):
                    errors[code] = "Number of needles must be a positive whole number."
                    continue
            else:
                # Lengths and diameters must be positive decimal values (> 0)
                try:
                    num_val = float(val)
                    if num_val <= 0:
                        errors[code] = f"{label} must be a positive decimal value."
                        continue
                except (ValueError, TypeError):
                    errors[code] = f"{label} must be a valid numeric value."
                    continue

            # Check min and max limits
            min_limit = rule.get_minimum_value()
            max_limit = rule.get_maximum_value()
            unit_str = f" {rule.measurement_definition.unit}" if rule.measurement_definition.unit else ""

            if min_limit is not None and num_val < min_limit:
                errors[code] = f"{label} must be at least {min_limit}{unit_str}."
            elif max_limit is not None and num_val > max_limit:
                errors[code] = f"{label} cannot exceed {max_limit}{unit_str}."

    return errors
