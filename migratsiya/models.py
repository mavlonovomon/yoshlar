from django.db import models
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
from core.models import Yosh


class MigrationYouth(models.Model):
    REASON_CHOICES = [
        ('DAM_OLISH', 'Dam olish'),
        ('ISH', 'Ish'),
        ('TALIM', "Ta'lim olish"),
        ('DAVOLANISH', 'Davolanish'),
        ('YASHASH', 'Yashash'),
    ]

    yosh = models.OneToOneField(
        Yosh,
        on_delete=models.CASCADE,
        related_name='migration_profile',
        verbose_name="Yosh"
    )
    departure_date = models.DateField(verbose_name="Chiqib ketgan sana")
    destination_country = models.CharField(max_length=100, verbose_name="Davlat")
    destination_province = models.CharField(max_length=100, blank=True, null=True, verbose_name="Provinsiya")
    destination_address = models.CharField(max_length=255, blank=True, null=True, verbose_name="Manzil")
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, verbose_name="Chiqib ketish sababi")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Qo'shilgan vaqti")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Tahrirlangan vaqti")

    class Meta:
        verbose_name = "Migratsiyadagi yosh"
        verbose_name_plural = "Migratsiyadagi yoshlar"

    def __str__(self):
        return self.yosh.fullname


class MigrationMeeting(models.Model):
    migration_youth = models.ForeignKey(
        MigrationYouth,
        on_delete=models.CASCADE,
        related_name='meetings',
        verbose_name="Migratsiyadagi yosh"
    )
    meeting_date = models.DateTimeField(verbose_name="Suhbat vaqti")
    photo = models.ImageField(
        upload_to='migratsiya/meetings/',
        verbose_name="Suhbat rasmi yoki skrinshoti",
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])]
    )
    return_date = models.DateField(blank=True, null=True, verbose_name="Qachon qaytmoqchi")

    work_title = models.CharField(max_length=255, blank=True, null=True, verbose_name="Qanday ishda ishlaydi")
    work_income = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Qancha pul topadi (oylik)"
    )
    work_conditions_rating = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name="Ish sharoiti (1-10)"
    )

    education_institution = models.CharField(max_length=255, blank=True, null=True, verbose_name="Qaysi dargohda")
    education_direction = models.CharField(max_length=255, blank=True, null=True, verbose_name="Qaysi yo'nalishda")
    education_course = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Nechanchi kurs")
    description = models.TextField(blank=True, null=True, verbose_name="Izoh")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Suhbat"
        verbose_name_plural = "Suhbatlar"
        ordering = ['-meeting_date']

    def __str__(self):
        return f"{self.migration_youth.yosh.fullname} - {self.meeting_date.strftime('%Y-%m-%d')}"
