from django.contrib import admin
from .models import ComplianceReason

@admin.register(ComplianceReason)
class ComplianceReasonAdmin(admin.ModelAdmin):
    list_display = (
        'display_order', 'reason_name', 'reason_code',
        'applicable_to_not_started', 'applicable_to_on_hold', 'applicable_to_discontinued',
        'is_active'
    )
    list_display_links = ('reason_name',)
    list_editable = (
        'display_order', 'applicable_to_not_started', 'applicable_to_on_hold', 'applicable_to_discontinued',
        'is_active'
    )
    search_fields = ('reason_name', 'reason_code')
    list_filter = ('is_active', 'applicable_to_not_started', 'applicable_to_on_hold', 'applicable_to_discontinued')

