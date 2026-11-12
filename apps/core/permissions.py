"""
Role-Based Access Control (RBAC) & Permissions Helper Module
Defines centralized authority checks for clinical and administrative operations.
"""

from typing import Dict, List, Any


def is_admin_user(user) -> bool:
    """
    Returns True only if the user is an Administrator:
    - Superuser (Django auth.User is_superuser)
    - User whose assigned Role profile is 'Admin'
    - User whose assigned Role profile possesses core administrative management capabilities
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    if profile and profile.role:
        r_name = (profile.role.role_name or '').strip().lower()
        if r_name == 'admin':
            return True
        if profile.role.cap_manage_users and profile.role.cap_manage_roles:
            return True
    # If is_staff is True without a restricting non-admin role
    if user.is_staff:
        if profile and profile.role:
            return profile.role.role_name.strip().lower() == 'admin'
        return True
    return False


def can_delete_patient(user) -> bool:
    """
    Only administrators (or roles explicitly granted cap_delete_records) can delete patients.
    Non-admin users cannot delete patient records.
    """
    if is_admin_user(user):
        return True
    profile = getattr(user, 'profile', None)
    if profile and profile.role and profile.role.is_active:
        return bool(profile.role.cap_delete_records)
    return False


def can_manage_users(user) -> bool:
    """
    Only administrators (or roles explicitly granted cap_manage_users) can manage user accounts.
    """
    if is_admin_user(user):
        return True
    profile = getattr(user, 'profile', None)
    if profile and profile.role and profile.role.is_active:
        return bool(profile.role.cap_manage_users)
    return False


def can_export_data(user) -> bool:
    """
    Only administrators (or roles explicitly granted cap_export_data) can export patient data.
    """
    if is_admin_user(user):
        return True
    profile = getattr(user, 'profile', None)
    if profile and profile.role and profile.role.is_active:
        return bool(profile.role.cap_export_data)
    return False


def can_manage_roles(user) -> bool:
    """
    Only administrators (or roles explicitly granted cap_manage_roles) can access the Roles & Privileges Dashboard.
    """
    if is_admin_user(user):
        return True
    profile = getattr(user, 'profile', None)
    if profile and profile.role and profile.role.is_active:
        return bool(profile.role.cap_manage_roles)
    return False


# 16 Granular Capability Definitions grouped by category
ROLE_CAPABILITY_CATEGORIES: List[Dict[str, Any]] = [
    {
        'category': 'Administrative & Security (Restricted)',
        'description': 'High-privilege actions restricted to system administrators',
        'badge_color': '#b00000',
        'capabilities': [
            {
                'field': 'cap_delete_records',
                'label': 'Delete Patient Records',
                'description': 'Authority to soft-delete patient profiles and clinical records.',
                'admin_only_default': True,
            },
            {
                'field': 'cap_manage_users',
                'label': 'User Management',
                'description': 'Authority to create, edit, activate, deactivate user accounts.',
                'admin_only_default': True,
            },
            {
                'field': 'cap_manage_roles',
                'label': 'Privileges & Roles Dashboard',
                'description': 'Authority to view and configure role capability permissions.',
                'admin_only_default': True,
            },
            {
                'field': 'cap_export_data',
                'label': 'Export Patient Data',
                'description': 'Authority to download Wide-format and Longitudinal Event CSVs.',
                'admin_only_default': True,
            },
            {
                'field': 'cap_approve',
                'label': 'Approve Treatment Courses',
                'description': 'Formal clinical authority to approve and lock treatment plans.',
                'admin_only_default': False,
            },
            {
                'field': 'cap_unlock_approved',
                'label': 'Unlock Approved Courses',
                'description': 'Authority to unlock previously locked treatment plans for revisions.',
                'admin_only_default': True,
            },
        ],
    },
    {
        'category': 'Clinical Documentation & Workflows',
        'description': 'Day-to-day data entry and clinical review permissions',
        'badge_color': '#006622',
        'capabilities': [
            {
                'field': 'cap_register_patient',
                'label': 'Register Patients',
                'description': 'Create new patient records in the system.',
                'admin_only_default': False,
            },
            {
                'field': 'cap_edit_demographics',
                'label': 'Edit Demographics',
                'description': 'Modify existing patient registration and demographic details.',
                'admin_only_default': False,
            },
            {
                'field': 'cap_enter_clinical',
                'label': 'Clinical History & Pelvic Exam',
                'description': 'Enter clinical history, physical exams, and IBS SVG diagrams.',
                'admin_only_default': False,
            },
            {
                'field': 'cap_enter_investigations',
                'label': 'Diagnostic Investigations',
                'description': 'Record Blood, Pathology, Imaging (MRI/CT), and Molecular tests.',
                'admin_only_default': False,
            },
            {
                'field': 'cap_enter_treatment',
                'label': 'Systemic Chemo & Radiotherapy',
                'description': 'Log NACT, EBRT fractions, and Adjuvant Chemotherapy courses.',
                'admin_only_default': False,
            },
            {
                'field': 'cap_enter_dosimetry',
                'label': 'Brachytherapy Dosimetry',
                'description': 'Log brachy applications, dwell times, and 2cc OAR organ doses.',
                'admin_only_default': False,
            },
            {
                'field': 'cap_enter_followup',
                'label': 'Follow-Up & Surveillance',
                'description': 'Record longitudinal follow-up visits, recurrence, and survival.',
                'admin_only_default': False,
            },
        ],
    },
    {
        'category': 'General System Access',
        'description': 'Baseline system navigation and read-only viewing permissions',
        'badge_color': '#003366',
        'capabilities': [
            {
                'field': 'cap_login',
                'label': 'System Login',
                'description': 'Ability to authenticate and access the application.',
                'admin_only_default': False,
            },
            {
                'field': 'cap_view_patients',
                'label': 'View Patient Worklist & Dashboards',
                'description': 'Access the main patient worklist and single patient dashboards.',
                'admin_only_default': False,
            },
            {
                'field': 'cap_view_reports',
                'label': 'View Reports & PDF Summaries',
                'description': 'Access patient summary views and download PDF reports.',
                'admin_only_default': False,
            },
        ],
    },
]

ALL_CAPABILITY_FIELDS = [
    cap['field']
    for cat in ROLE_CAPABILITY_CATEGORIES
    for cap in cat['capabilities']
]
