from django.utils import timezone


def module_alert_counts(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {
            "active_surveys_count": 0,
            "active_tests_count": 0,
            "has_active_surveys": False,
            "has_active_tests": False,
        }

    from bilim_sinovi.models import TestConfig
    from sorovnoma.models import Survey, SurveyStatus

    now = timezone.now()
    active_surveys_count = Survey.objects.filter(status=SurveyStatus.ACTIVE).count()
    active_tests_count = TestConfig.objects.filter(
        is_active=True,
        start_time__lte=now,
        end_time__gte=now,
    ).count()

    return {
        "active_surveys_count": active_surveys_count,
        "active_tests_count": active_tests_count,
        "has_active_surveys": active_surveys_count > 0,
        "has_active_tests": active_tests_count > 0,
    }
