from django.db import models
from django.core.validators import FileExtensionValidator
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils import timezone
from PIL import Image
from io import BytesIO
import logging
from core.models import Mahalla

logger = logging.getLogger(__name__)


class FiveInitiativeEvent(models.Model):
    DIRECTION_CHOICES = [
        ('SPORT', 'Sport'),
        ('KASB', 'Kasblar tanlovi'),
        ('KITOB', 'Kitobxonlik'),
        ('SANAT', "San'at va madaniyat"),
        ('INTEL', "Intelektual o'yinlar"),
        ('KIBER', 'Kibersport'),
    ]

    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES, verbose_name="Tadbir yo'nalishi")
    title = models.CharField(max_length=255, verbose_name="Tadbir nomi")
    event_date = models.DateField(verbose_name="O'tkazilgan sana")
    mahalla = models.ForeignKey(Mahalla, on_delete=models.CASCADE, related_name='five_initiative_events', verbose_name="Mahalla")
    coverage = models.PositiveIntegerField(verbose_name="Qamrov")
    description = models.TextField(blank=True, null=True, verbose_name="Izoh")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Qo'shilgan vaqti")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Tahrirlangan vaqti")

    class Meta:
        ordering = ['-event_date', '-created_at']
        verbose_name = "5 tashabbus tadbiri"
        verbose_name_plural = "5 tashabbus tadbirlari"

    def __str__(self):
        return f"{self.title} - {self.mahalla.name}"


class FiveInitiativePhoto(models.Model):
    event = models.ForeignKey(
        FiveInitiativeEvent,
        on_delete=models.CASCADE,
        related_name='photos',
        verbose_name="Tadbir"
    )
    image = models.ImageField(
        upload_to='beshtashabbus/photos/',
        verbose_name="Rasm",
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tadbir rasmi"
        verbose_name_plural = "Tadbir rasmlari"

    def save(self, *args, **kwargs):
        if self.image:
            try:
                from django.core.files.uploadedfile import UploadedFile
                if isinstance(self.image.file, UploadedFile):
                    img = Image.open(self.image)
                    if self.image.size > 512 * 1024:
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")

                        output = BytesIO()
                        if img.width > 1600 or img.height > 1600:
                            img.thumbnail((1600, 1600))

                        img.save(output, format='JPEG', quality=70)
                        output.seek(0)

                        import os
                        name = os.path.basename(self.image.name)
                        name = os.path.splitext(name)[0] + ".jpg"

                        self.image = InMemoryUploadedFile(
                            output,
                            'image',
                            name,
                            'image/jpeg',
                            output.getbuffer().nbytes,
                            None
                        )
            except Exception as exc:
                logger.error("Five initiative photo processing error: %s", exc)

        super().save(*args, **kwargs)


class FiveInitiativeApplicationSnapshot(models.Model):
    """5 tashabbus arizalari import snapshoti."""
    year = models.PositiveSmallIntegerField(default=2026, db_index=True, verbose_name="Yil")
    source_file_name = models.CharField(max_length=255, verbose_name="Yuklangan fayl")
    uploaded_by = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='five_initiative_application_snapshots',
        verbose_name="Yuklagan foydalanuvchi",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Yuklangan vaqt")
    raw_meta = models.JSONField(default=dict, blank=True, verbose_name="Import meta")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "5 tashabbus ariza snapshoti"
        verbose_name_plural = "5 tashabbus ariza snapshotlari"

    def __str__(self):
        return f"{self.year} | {timezone.localtime(self.created_at):%d.%m.%Y %H:%M}"


class FiveInitiativeApplicationEntry(models.Model):
    """Snapshot ichidagi tozalangan ariza qatori."""
    snapshot = models.ForeignKey(
        FiveInitiativeApplicationSnapshot,
        on_delete=models.CASCADE,
        related_name='entries',
        verbose_name="Snapshot",
    )
    region = models.CharField(max_length=150, blank=True, default="", verbose_name="Viloyat")
    district = models.CharField(max_length=150, blank=True, default="", verbose_name="Tuman")
    sector = models.CharField(max_length=150, blank=True, default="", verbose_name="Sektor")
    mahalla = models.ForeignKey(
        Mahalla,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='five_initiative_application_entries',
        verbose_name="Mahalla",
    )
    mahalla_name_raw = models.CharField(max_length=255, verbose_name="Mahalla (xom)")
    participant_name = models.CharField(max_length=255, verbose_name="Ishtirokchi F.I.O")
    pinfl = models.CharField(max_length=14, db_index=True, verbose_name="PINFL")
    gender = models.CharField(max_length=30, blank=True, default="", verbose_name="Jinsi")
    age_category = models.CharField(max_length=80, blank=True, default="", verbose_name="Yosh toifasi")
    selection_category = models.CharField(max_length=120, db_index=True, verbose_name="Kategoriya")
    direction = models.CharField(max_length=120, db_index=True, verbose_name="Yo'nalish")

    class Meta:
        ordering = ['mahalla_name_raw', 'participant_name']
        verbose_name = "5 tashabbus ariza qatori"
        verbose_name_plural = "5 tashabbus ariza qatorlari"
        permissions = [
            ("submit_application", "5 tashabbus ariza yuborish ruxsati"),
        ]
        indexes = [
            models.Index(fields=['snapshot', 'mahalla']),
            models.Index(fields=['snapshot', 'selection_category']),
            models.Index(fields=['snapshot', 'direction']),
            models.Index(fields=['snapshot', 'pinfl']),
        ]


class FiveInitiativeSvodNorm(models.Model):
    """5 tashabbus svod jadvali uchun norma qatori.

    Har bir qator 4 ta ustun (kategoriya, yo'nalish, yosh toifasi, jins)
    bo'yicha aniqlangan norma qiymatini saqlaydi.
    Agar gender bo'sh bo'lsa – erkak + ayol qo'shib hisoblanadi.
    """
    selection_category = models.CharField(max_length=150, verbose_name="Kategoriya")
    direction = models.CharField(max_length=150, verbose_name="Yo'nalish")
    age_category = models.CharField(max_length=100, verbose_name="Yosh toifasi")
    gender = models.CharField(
        max_length=30, blank=True, default="",
        verbose_name="Jinsi",
        help_text="Bo'sh bo'lsa erkak+ayol qo'shiladi",
    )
    norma = models.PositiveIntegerField(default=0, verbose_name="Norma")
    row_order = models.PositiveIntegerField(default=0, verbose_name="Tartib raqami")

    class Meta:
        ordering = ['row_order', 'selection_category', 'direction']
        verbose_name = "5 tashabbus svod norma"
        verbose_name_plural = "5 tashabbus svod normalari"
        unique_together = ('selection_category', 'direction', 'age_category', 'gender')

    def __str__(self):
        parts = [self.selection_category, self.direction, self.age_category]
        if self.gender:
            parts.append(self.gender)
        return " | ".join(parts) + f" (norma={self.norma})"
