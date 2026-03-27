from django.db import models
from django.core.validators import FileExtensionValidator


class CreditCandidate(models.Model):
    STAGE_CHOICES = [
        ("NOMINATION", "Nomzod"),
        ("IN_PROCESS", "Jarayonda"),
        ("APPROVED", "Kredit ajratildi"),
        ("REJECTED", "Rad etildi"),
        ("MONITORING", "Monitoring"),
    ]
    DECISION_BASIS_CHOICES = [
        ("PQ60", "PQ-60"),
        ("PQ61", "PQ-61"),
        ("PQ62", "PQ-62"),
    ]
    COLLATERAL_TYPE_CHOICES = [
        ("NONE", "Garovsiz"),
        ("COLLATERAL", "Garov bilan"),
        ("GUARANTOR", "Kafillik bilan"),
        ("INSURANCE", "Sug'urta polisi bilan"),
    ]
    BUSINESS_TYPE_CHOICES = [
        ("PRODUCTION", "Ishlab chiqarish"),
        ("SERVICE", "Xizmat ko'rsatish"),
    ]

    yosh = models.ForeignKey("core.Yosh", on_delete=models.CASCADE, related_name="credit_candidates")
    created_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credit_candidates_created",
    )
    processed_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credit_candidates_processed",
    )

    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default="NOMINATION", db_index=True)
    monitoring_enabled = models.BooleanField(default=False)

    business_name = models.CharField(max_length=255, blank=True, default="")
    business_type = models.CharField(max_length=20, choices=BUSINESS_TYPE_CHOICES, blank=True, default="")
    project_goal = models.CharField(max_length=500, blank=True, default="")
    collateral = models.CharField(max_length=255, blank=True, default="")
    collateral_type = models.CharField(max_length=20, choices=COLLATERAL_TYPE_CHOICES, blank=True, default="")
    requested_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    credit_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    reject_reason = models.CharField(max_length=500, blank=True, default="")
    monitoring_note = models.TextField(blank=True, default="")
    decision_basis = models.CharField(max_length=10, choices=DECISION_BASIS_CHOICES, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Kredit nomzodi"
        verbose_name_plural = "Kredit nomzodlari"
        permissions = [
            ("manage_pipeline", "Kredit jarayonini boshqarish"),
        ]

    def __str__(self):
        return f"{self.yosh.fullname} ({self.get_stage_display()})"


class CreditMonitoringEntry(models.Model):
    candidate = models.ForeignKey(
        CreditCandidate, on_delete=models.CASCADE, related_name="monitoring_entries"
    )
    created_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credit_monitoring_entries",
    )
    monitoring_date = models.DateField()
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-monitoring_date", "-created_at"]
        verbose_name = "Kredit monitoring yozuvi"
        verbose_name_plural = "Kredit monitoring yozuvlari"

    def __str__(self):
        return f"{self.candidate_id} | {self.monitoring_date}"


class CreditMonitoringFile(models.Model):
    FILE_TYPE_CHOICES = [
        ("image", "Rasm"),
        ("document", "Hujjat"),
    ]

    monitoring_entry = models.ForeignKey(
        CreditMonitoringEntry, on_delete=models.CASCADE, related_name="files"
    )
    file = models.FileField(
        upload_to="kredit_yo_naltirish/monitoring/",
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "pdf"])],
    )
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Monitoring fayli"
        verbose_name_plural = "Monitoring fayllari"
