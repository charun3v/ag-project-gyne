from django.apps import AppConfig


class FollowupConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'followup'

    def ready(self):
        try:
            from django.db.models import Q
            from .models import FollowUpStatus
            # Automatically repair any follow-up records that were mistakenly flagged as deceased due to bool("0")
            FollowUpStatus.objects.filter(
                death_reported=True
            ).filter(
                Q(disease_status__status_name__icontains='NED') |
                Q(disease_status__status_name__icontains='No Evidence') |
                Q(disease_status__status_name__icontains='Alive')
            ).exclude(
                disease_status__status_name__icontains='dead'
            ).update(
                death_reported=False,
                date_of_death=None,
                cause_of_death=None
            )
        except Exception:
            pass

