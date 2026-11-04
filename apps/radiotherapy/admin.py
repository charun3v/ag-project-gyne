from django.contrib import admin
from .models import (
    ApplicatorType,
    ApplicatorMeasurementDefinition,
    ApplicatorFieldRule,
    BrachySession,
    BrachyCourse,
    BrachyFraction,
    EBRTCourse,
)


class ApplicatorFieldRuleInline(admin.TabularInline):
    model = ApplicatorFieldRule
    extra = 0
    fields = ('measurement_definition', 'enabled', 'required', 'display_order', 'min_value_override', 'max_value_override')
    ordering = ('display_order', 'id')


@admin.register(ApplicatorType)
class ApplicatorTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'active', 'display_order', 'rule_summary')
    list_editable = ('active', 'display_order')
    search_fields = ('name',)
    inlines = [ApplicatorFieldRuleInline]

    def rule_summary(self, obj):
        rules = obj.field_rules.filter(enabled=True).select_related('measurement_definition')
        req = [r.measurement_definition.label for r in rules if r.required]
        opt = [r.measurement_definition.label for r in rules if not r.required]
        parts = []
        if req:
            parts.append(f"Required: {', '.join(req)}")
        if opt:
            parts.append(f"Optional: {', '.join(opt)}")
        return " | ".join(parts) if parts else "No measurements enabled"
    rule_summary.short_description = "Active Measurement Rules"


@admin.register(ApplicatorMeasurementDefinition)
class ApplicatorMeasurementDefinitionAdmin(admin.ModelAdmin):
    list_display = ('code', 'label', 'data_type', 'unit', 'minimum_value', 'maximum_value', 'active', 'display_order')
    list_editable = ('active', 'display_order', 'minimum_value', 'maximum_value')
    search_fields = ('code', 'label')


@admin.register(ApplicatorFieldRule)
class ApplicatorFieldRuleAdmin(admin.ModelAdmin):
    list_display = ('applicator_type', 'measurement_definition', 'enabled', 'required', 'display_order', 'min_value_override', 'max_value_override')
    list_filter = ('applicator_type', 'enabled', 'required')
    list_editable = ('enabled', 'required', 'display_order', 'min_value_override', 'max_value_override')
    search_fields = ('applicator_type__name', 'measurement_definition__label', 'measurement_definition__code')


@admin.register(BrachySession)
class BrachySessionAdmin(admin.ModelAdmin):
    list_display = ('brachy_session_id', 'brachy_course', 'session_number', 'session_date', 'applicator', 'is_approved', 'approval_locked')
    list_filter = ('applicator', 'is_approved', 'approval_locked')
    search_fields = ('brachy_course__patient__mr_no', 'brachy_course__patient__pt_name', 'procedure_performed_by')
