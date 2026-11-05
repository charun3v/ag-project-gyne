from django import forms
from django.core.exceptions import ValidationError
from .models import (
    BrachySession,
    ApplicatorType,
    BrachyImageGuidance,
    AnaesthesiaType,
    BrachySessionStatus,
    ApplicatorFieldRule,
)
from .validators import validate_applicator_measurements, ALL_MEASUREMENT_CODES


class BrachySessionForm(forms.ModelForm):
    """
    Form for creating and editing Brachytherapy Sessions with
    configurable, applicator-dependent validation.
    """
    procedure_performed_by = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'access-input'})
    )
    procedure_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'access-textarea', 'rows': 2})
    )
    insertion_complications = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'access-textarea', 'rows': 2})
    )
    fractions_planned = forms.IntegerField(
        required=False,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'access-input'})
    )

    # Expose needle_count explicitly as integer field
    needle_count = forms.IntegerField(
        required=False,
        label="Number of needles",
        widget=forms.NumberInput(attrs={'class': 'access-input', 'placeholder': 'e.g. 12', 'min': 1})
    )

    class Meta:
        model = BrachySession
        fields = [
            'session_number',
            'session_date',
            'applicator',
            'image_guidance',
            'anaesthesia_type',
            'session_status',
            'procedure_performed_by',
            'procedure_notes',
            'insertion_complications',
            'tandem_length_cm',
            'ovoid_diameter_mm',
            'ovoid_length_mm',
            'ring_diameter_mm',
            'needle_count',
            'packing_adequate',
            'imaging_done',
            'fractions_planned',
        ]
        widgets = {
            'session_number': forms.NumberInput(attrs={'class': 'access-input'}),
            'session_date': forms.DateInput(attrs={'class': 'access-input', 'type': 'date'}),
            'applicator': forms.Select(attrs={'class': 'access-select', 'id': 'id_applicator', 'onchange': 'onApplicatorChange(this)'}),
            'image_guidance': forms.Select(attrs={'class': 'access-select'}),
            'anaesthesia_type': forms.Select(attrs={'class': 'access-select'}),
            'session_status': forms.Select(attrs={'class': 'access-select'}),
            'procedure_performed_by': forms.TextInput(attrs={'class': 'access-input'}),
            'procedure_notes': forms.Textarea(attrs={'class': 'access-textarea', 'rows': 2}),
            'insertion_complications': forms.Textarea(attrs={'class': 'access-textarea', 'rows': 2}),
            'tandem_length_cm': forms.NumberInput(attrs={'class': 'access-input', 'step': '0.1', 'placeholder': 'e.g. 6.0'}),
            'ovoid_diameter_mm': forms.NumberInput(attrs={'class': 'access-input', 'step': '0.1', 'placeholder': 'e.g. 20'}),
            'ovoid_length_mm': forms.NumberInput(attrs={'class': 'access-input', 'step': '0.1', 'placeholder': 'e.g. 30'}),
            'ring_diameter_mm': forms.NumberInput(attrs={'class': 'access-input', 'step': '0.1', 'placeholder': 'e.g. 30'}),
        }

    def __init__(self, *args, **kwargs):
        self.course = kwargs.pop('course', None)
        super().__init__(*args, **kwargs)
        self.fields['applicator'].queryset = ApplicatorType.objects.filter(active=True)
        self.fields['image_guidance'].queryset = BrachyImageGuidance.objects.filter(is_active=True)
        self.fields['anaesthesia_type'].queryset = AnaesthesiaType.objects.filter(is_active=True)
        self.fields['session_status'].queryset = BrachySessionStatus.objects.filter(is_active=True)

        # Set default values if new instance
        if not self.instance.pk:
            self.fields['packing_adequate'].initial = True
            self.fields['imaging_done'].initial = True
            self.fields['session_number'].initial = 1

    def clean(self):
        from datetime import date
        cleaned_data = super().clean()

        if not cleaned_data.get('fractions_planned'):
            cleaned_data['fractions_planned'] = 1

        # 1. Check approval lock
        if self.instance.pk and self.instance.approval_locked:
            raise ValidationError("This brachytherapy session is formally approved and locked against editing.")

        # 2. Date validations: cannot be a future date; Session 2 must be after Session 1
        session_date = cleaned_data.get('session_date')
        if session_date:
            if session_date > date.today():
                self.add_error('session_date', f"Session insertion date ({session_date.strftime('%d-%b-%Y')}) cannot be a future date.")

            # Chronology check with other sessions in the same course
            course = getattr(self, 'course', None) or getattr(self.instance, 'brachy_course', None)
            if course:
                s_num = cleaned_data.get('session_number') or getattr(self.instance, 'session_number', 1)

                # Prior sessions (e.g. Session 1 when evaluating Session 2):
                prior_sessions = course.sessions.filter(
                    session_number__lt=s_num
                ).exclude(pk=self.instance.pk).order_by('-session_number')
                for ps in prior_sessions:
                    if ps.session_date and session_date <= ps.session_date:
                        self.add_error(
                            'session_date',
                            f"Application #{s_num} date ({session_date.strftime('%d-%b-%Y')}) must be strictly after Application #{ps.session_number} date ({ps.session_date.strftime('%d-%b-%Y')})."
                        )
                        break

                # Subsequent sessions (e.g. Session 2 when editing Session 1):
                next_sessions = course.sessions.filter(
                    session_number__gt=s_num
                ).exclude(pk=self.instance.pk).order_by('session_number')
                for ns in next_sessions:
                    if ns.session_date and session_date >= ns.session_date:
                        self.add_error(
                            'session_date',
                            f"Application #{s_num} date ({session_date.strftime('%d-%b-%Y')}) must be strictly before Application #{ns.session_number} date ({ns.session_date.strftime('%d-%b-%Y')})."
                        )
                        break

        applicator = cleaned_data.get('applicator')
        if not applicator:
            return cleaned_data

        # 2. Check if completing session
        status = cleaned_data.get('session_status')
        is_completing = status and (getattr(status, 'status_name', '').lower() == 'completed' or getattr(status, 'status_id', 0) == 2)

        # 3. Server-side validation against active ApplicatorFieldRule configurations
        is_historical = bool(self.instance.pk and self.instance.is_approved)
        errors = validate_applicator_measurements(
            applicator_type=applicator,
            data=cleaned_data,
            is_historical_approved=is_historical,
            is_completing_or_approving=is_completing
        )

        for code, err_msg in errors.items():
            if code in self.fields:
                self.add_error(code, err_msg)
            else:
                self.add_error(None, err_msg)

        # 4. Clear values not enabled for this applicator so they are not saved accidentally
        active_rules = ApplicatorFieldRule.objects.filter(
            applicator_type=applicator,
            measurement_definition__active=True
        ).select_related('measurement_definition')
        enabled_codes = {r.measurement_definition.code for r in active_rules if r.enabled}

        for code in ALL_MEASUREMENT_CODES:
            if code not in enabled_codes:
                if code == 'needle_count':
                    cleaned_data[code] = 0
                else:
                    cleaned_data[code] = None

        return cleaned_data
