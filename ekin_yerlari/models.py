from django.db import models
from django.utils import timezone

from core.models import Yosh


class EkinYerSnapshot(models.Model):
    source_file_name = models.CharField(max_length=255, verbose_name="Manba fayl")
    uploaded_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ekin_yer_snapshots",
        verbose_name="Yuklagan foydalanuvchi",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Yuklangan vaqt")
    raw_meta = models.JSONField(default=dict, blank=True, verbose_name="Import meta")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Ekin yerlari snapshot"
        verbose_name_plural = "Ekin yerlari snapshotlar"

    def __str__(self):
        return f"Ekin yerlari | {timezone.localtime(self.created_at):%d.%m.%Y %H:%M}"


class EkinYerEntry(models.Model):
    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"

    MATCH_STATUS_CHOICES = [
        (MATCHED, "Topildi"),
        (AMBIGUOUS, "Noaniq"),
        (NOT_FOUND, "Topilmadi"),
    ]

    snapshot = models.ForeignKey(
        EkinYerSnapshot,
        on_delete=models.CASCADE,
        related_name="entries",
        verbose_name="Snapshot",
    )
    source_entry_id = models.CharField(max_length=64, blank=True, default="", db_index=True, verbose_name="Source ID")
    winner_external_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        verbose_name="G'olib source ID",
    )
    winner_name = models.CharField(max_length=255, db_index=True, verbose_name="F.I.Sh")
    winner_name_normalized = models.CharField(max_length=255, db_index=True, verbose_name="F.I.Sh (norm)")
    winner_birth_date = models.DateField(null=True, blank=True, db_index=True, verbose_name="Tug'ilgan sana")
    winner_phone = models.CharField(max_length=30, blank=True, default="", verbose_name="Telefon")
    winner_neighborhood_name = models.CharField(max_length=255, blank=True, default="", verbose_name="Yashash mahallasi")
    land_neighborhood_id = models.BigIntegerField(null=True, blank=True, db_index=True, verbose_name="Yer mahalla ID")
    land_neighborhood_name = models.CharField(max_length=255, blank=True, default="", db_index=True, verbose_name="Yer mahallasi")
    area = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, verbose_name="Maydon")
    area_specialization = models.CharField(max_length=255, blank=True, default="", verbose_name="Yo'nalish")
    specialty_category = models.CharField(max_length=255, blank=True, default="", verbose_name="Kategoriya")
    specialty_type = models.CharField(max_length=255, blank=True, default="", verbose_name="Ekin turi")
    contour_numbers = models.JSONField(default=list, blank=True, verbose_name="Konturlar")
    land_type = models.JSONField(default=list, blank=True, verbose_name="Yer turi")
    geometry = models.JSONField(default=dict, blank=True, verbose_name="Geometriya")
    location = models.JSONField(default=dict, blank=True, verbose_name="Joylashuv")
    raw_json = models.JSONField(default=dict, blank=True, verbose_name="Xom yozuv")
    linked_yosh = models.ForeignKey(
        Yosh,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ekin_yer_entries",
        verbose_name="Bog'langan yosh",
    )
    match_status = models.CharField(
        max_length=20,
        choices=MATCH_STATUS_CHOICES,
        default=NOT_FOUND,
        db_index=True,
        verbose_name="Moslash holati",
    )
    match_note = models.CharField(max_length=255, blank=True, default="", verbose_name="Moslash izohi")
    possible_matches = models.JSONField(default=list, blank=True, verbose_name="Ehtimoliy mosliklar")
    is_youth_age = models.BooleanField(default=False, db_index=True, verbose_name="Yosh toifasida")

    class Meta:
        ordering = ["land_neighborhood_name", "winner_name"]
        verbose_name = "Ekin yer yozuvi"
        verbose_name_plural = "Ekin yer yozuvlari"
        indexes = [
            models.Index(fields=["snapshot", "match_status"]),
            models.Index(fields=["snapshot", "linked_yosh"]),
            models.Index(fields=["snapshot", "land_neighborhood_name"]),
        ]

    def __str__(self):
        return self.winner_name

