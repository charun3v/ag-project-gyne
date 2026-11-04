from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Role(models.Model):
    """Corresponds to sbtblRole - Granular RBAC permissions."""
    role_id = models.IntegerField(primary_key=True, help_text="Original RoleID from Access")
    role_name = models.CharField(max_length=100, unique=True)
    role_description = models.CharField(max_length=255, blank=True, null=True)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    # 16 Granular Capability Flags matching MS Access sbtblRole
    cap_login = models.BooleanField(default=True)
    cap_view_patients = models.BooleanField(default=True)
    cap_register_patient = models.BooleanField(default=False)
    cap_edit_demographics = models.BooleanField(default=False)
    cap_enter_clinical = models.BooleanField(default=False)
    cap_enter_investigations = models.BooleanField(default=False)
    cap_enter_treatment = models.BooleanField(default=False)
    cap_enter_dosimetry = models.BooleanField(default=False)
    cap_enter_followup = models.BooleanField(default=False)
    cap_approve = models.BooleanField(default=False)
    cap_unlock_approved = models.BooleanField(default=False)
    cap_delete_records = models.BooleanField(default=False)
    cap_manage_users = models.BooleanField(default=False)
    cap_manage_roles = models.BooleanField(default=False)
    cap_view_reports = models.BooleanField(default=True)
    cap_export_data = models.BooleanField(default=False)

    class Meta:
        db_table = 'sbtblRole'
        ordering = ['display_order', 'role_name']

    def __str__(self):
        return self.role_name


class UserProfile(models.Model):
    """Extends Django auth.User with Access tblUsers fields."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    user_level = models.CharField(max_length=50, blank=True, null=True)
    failed_login_count = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_failed_login = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'tblUsers'

    def __str__(self):
        return f"{self.user.username} ({self.role.role_name if self.role else 'No Role'})"


class State(models.Model):
    """tblStates"""
    state_id = models.IntegerField(primary_key=True)
    state_name = models.CharField(max_length=100)

    class Meta:
        db_table = 'tblStates'
        ordering = ['state_name']

    def __str__(self):
        return self.state_name


class District(models.Model):
    """tblDistricts"""
    district_id = models.IntegerField(primary_key=True)
    district_name = models.CharField(max_length=150)
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='districts', db_column='StateID')

    class Meta:
        db_table = 'tblDistricts'
        ordering = ['district_name']

    def __str__(self):
        return f"{self.district_name} ({self.state.state_name})"


class Consultant(models.Model):
    """tblConsultant"""
    consultant_id = models.IntegerField(primary_key=True)
    consultant_name = models.CharField(max_length=150)
    display_order = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'tblConsultant'
        ordering = ['display_order', 'consultant_name']

    def __str__(self):
        return self.consultant_name


class AuditLog(models.Model):
    """tblAuditLog - Clinical compliance audit trail"""
    log_id = models.BigAutoField(primary_key=True)
    log_datetime = models.DateTimeField(default=timezone.now)
    username = models.CharField(max_length=100)
    full_name = models.CharField(max_length=150, blank=True, null=True)
    action = models.CharField(max_length=50) # INSERT, UPDATE, DELETE, LOGIN, APPROVE
    table_affected = models.CharField(max_length=100, blank=True, null=True)
    record_ref = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    field_name = models.CharField(max_length=100, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    reason = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'tblAuditLog'
        ordering = ['-log_datetime']

    def __str__(self):
        return f"[{self.log_datetime.strftime('%Y-%m-%d %H:%M')}] {self.action} on {self.table_affected} by {self.username}"


class ApprovalAudit(models.Model):
    """tblApprovalAudit - Senior clinician sign-off audit"""
    approval_audit_id = models.BigAutoField(primary_key=True)
    form_name = models.CharField(max_length=100)
    record_key = models.CharField(max_length=100)
    mr_no = models.CharField(max_length=64, blank=True, null=True)
    approval_action = models.CharField(max_length=50) # Approved, Unlocked
    approver_username = models.CharField(max_length=100)
    approver_full_name = models.CharField(max_length=150, blank=True, null=True)
    approver_role = models.CharField(max_length=100)
    action_on = models.DateTimeField(default=timezone.now)
    requested_by = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'tblApprovalAudit'
        ordering = ['-action_on']


class AppSetting(models.Model):
    """tblAppSettings"""
    setting_id = models.AutoField(primary_key=True)
    setting_key = models.CharField(max_length=100, unique=True)
    setting_value = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'tblAppSettings'

    def __str__(self):
        return f"{self.setting_key} = {self.setting_value}"
