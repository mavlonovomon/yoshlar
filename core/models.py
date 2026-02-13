from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.contrib.auth.models import AbstractUser
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import logging

logger = logging.getLogger(__name__)

class Mahalla(models.Model):
    name = models.CharField(max_length=200, unique=True, verbose_name="Mahalla nomi", db_index=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Mahalla"
        verbose_name_plural = "Mahallalar"

    def __str__(self):
        return self.name

class User(AbstractUser):
    ROLE_CHOICES = (
        ('SUPER_ADMIN', 'Super Admin'),
        ('RAHBAR', 'Rahbar'),
        ('YETAKCHI', 'Yetakchi'),
    )
    SECTOR_CHOICES = (
        (1, '1-sektor'),
        (2, '2-sektor'),
        (3, '3-sektor'),
        (4, '4-sektor'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='YETAKCHI', verbose_name="Rol")
    full_name = models.CharField(max_length=255, verbose_name="F.I.Sh")
    pinfl = models.CharField(max_length=14, unique=True, null=True, blank=True, db_index=True, verbose_name="PINFL")
    phone_number = models.CharField(max_length=20, blank=True, verbose_name="Telefon raqami")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Tug'ilgan sana")
    mahalla = models.ForeignKey(Mahalla, on_delete=models.SET_NULL, null=True, blank=True, related_name='leaders', verbose_name="Mahalla")
    profile_image = models.ImageField(upload_to='profiles/', null=True, blank=True, verbose_name="Profil rasmi")
    position = models.CharField(max_length=120, blank=True, verbose_name="Lavozimi")
    address = models.CharField(max_length=500, blank=True, verbose_name="Yashash manzili")
    education = models.CharField(max_length=255, blank=True, verbose_name="Ta'lim")
    specialization = models.CharField(max_length=255, blank=True, verbose_name="Mutaxassisligi")
    work_start_date = models.DateField(null=True, blank=True, verbose_name="Ish boshlagan sana")
    telegram_username = models.CharField(max_length=100, blank=True, verbose_name="Telegram")
    emergency_contact = models.CharField(max_length=120, blank=True, verbose_name="Favqulodda aloqa")
    about = models.TextField(blank=True, verbose_name="Qo'shimcha ma'lumot")
    sector = models.PositiveSmallIntegerField(choices=SECTOR_CHOICES, null=True, blank=True, verbose_name="Sektor")
    is_sector_coordinator = models.BooleanField(default=False, verbose_name="Sektor koordinatori")

    def save(self, *args, **kwargs):
        if self.role != 'YETAKCHI':
            self.is_sector_coordinator = False
        if self.is_superuser:
            self.role = 'SUPER_ADMIN'
        if self.role in {'SUPER_ADMIN', 'RAHBAR'}:
            self.is_staff = True
        elif not self.is_superuser:
            self.is_staff = False
        super().save(*args, **kwargs)
        if self.is_sector_coordinator and self.sector:
            User.objects.filter(sector=self.sector, is_sector_coordinator=True).exclude(pk=self.pk).update(is_sector_coordinator=False)

    def clean(self):
        super().clean()
        if self.is_sector_coordinator and not self.sector:
            raise ValidationError({'sector': "Koordinator uchun sektor tanlang."})

    @property
    def is_leader(self):
        return self.role == 'YETAKCHI'
    
    @property
    def is_super_admin(self):
        return self.role == 'SUPER_ADMIN'

    @property
    def is_rahbar(self):
        return self.role == 'RAHBAR'

    @property
    def is_site_admin(self):
        return self.is_superuser or self.role in {'SUPER_ADMIN', 'RAHBAR'}


class LeaderKpiSnapshot(models.Model):
    """Yetakchi uchun ma'lum davr KPI natijalari snapshoti."""
    user = models.ForeignKey('core.User', on_delete=models.CASCADE, related_name='kpi_snapshots', db_index=True)
    date_from = models.DateField(db_index=True)
    date_to = models.DateField(db_index=True)
    block_scores = models.JSONField(default=dict, blank=True)
    total_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    debug_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_to', '-created_at']
        verbose_name = "Yetakchi KPI snapshot"
        verbose_name_plural = "Yetakchi KPI snapshotlar"
        unique_together = ('user', 'date_from', 'date_to')
        indexes = [
            models.Index(fields=['date_from', 'date_to']),
            models.Index(fields=['user', 'date_to']),
        ]

    def __str__(self):
        return f"{self.user.full_name or self.user.username}: {self.date_from} - {self.date_to}"


class Yosh(models.Model):
    fullname = models.CharField(max_length=255, verbose_name="F.I.Sh", db_index=True)
    birth_date = models.DateField(verbose_name="Tug'ilgan sana")
    passport_number = models.CharField(max_length=20, verbose_name="Pasport raqami", blank=True)
    jshshir = models.CharField(max_length=14, verbose_name="JSHSHIR", unique=True, db_index=True)
    address = models.CharField(max_length=500, verbose_name="Manzil")
    photo = models.ImageField(upload_to='yoshlar_photos/', verbose_name="Rasm", blank=True, null=True)
    phone_number = models.CharField(max_length=20, verbose_name="Telefon raqami", blank=True)
    mahalla = models.ForeignKey(Mahalla, on_delete=models.CASCADE, related_name='yoshlar', verbose_name="Mahalla")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fullname']
        verbose_name = "Yoshlar"
        verbose_name_plural = "Yoshlar"

    def __str__(self):
        return self.fullname
    
    def save(self, *args, **kwargs):
        if self.photo:
            try:
                # Only process if it's a new file (not already saved in storage)
                from django.core.files.uploadedfile import UploadedFile
                if isinstance(self.photo.file, UploadedFile):
                    img = Image.open(self.photo)
                    if self.photo.size > 512 * 1024:
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")
                        
                        output = BytesIO()
                        if img.width > 1600 or img.height > 1600:
                            img.thumbnail((1600, 1600))
                            
                        img.save(output, format='JPEG', quality=70)
                        output.seek(0)
                        
                        import os
                        name = os.path.basename(self.photo.name)
                        name = os.path.splitext(name)[0] + ".jpg"
                        
                        self.photo = InMemoryUploadedFile(
                            output, 'photo', name,
                            'image/jpeg', output.getbuffer().nbytes, None
                        )
            except Exception as e:
                logger.error(f"Image processing error for {self.fullname}: {str(e)}")
                
        super().save(*args, **kwargs)
    
    @property
    def last_meeting(self):
        return self.uchrashuvlar.order_by('-meeting_date').first()

class Uchrashuv(models.Model):
    yosh = models.ForeignKey(Yosh, on_delete=models.CASCADE, related_name='uchrashuvlar')
    yetakchi = models.ForeignKey(User, on_delete=models.CASCADE)
    meeting_date = models.DateTimeField(verbose_name="Suhbat vaqti")
    conversation_text = models.TextField(verbose_name="Suhbat mazmuni")
    photo = models.ImageField(
        upload_to='meetings/',
        blank=True,
        null=True,
        verbose_name="Suhbat rasmi",
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])]
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-meeting_date']
    
    def __str__(self):
        return f"{self.yosh.fullname} - {self.meeting_date.strftime('%Y-%m-%d')}"

    def save(self, *args, **kwargs):
        if self.photo:
            try:
                from django.core.files.uploadedfile import UploadedFile
                if isinstance(self.photo.file, UploadedFile):
                    img = Image.open(self.photo)
                    if self.photo.size > 512 * 1024:
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")

                        output = BytesIO()
                        if img.width > 1600 or img.height > 1600:
                            img.thumbnail((1600, 1600))

                        img.save(output, format='JPEG', quality=70)
                        output.seek(0)

                        import os
                        name = os.path.basename(self.photo.name)
                        name = os.path.splitext(name)[0] + ".jpg"

                        self.photo = InMemoryUploadedFile(
                            output, 'photo', name,
                            'image/jpeg', output.getbuffer().nbytes, None
                        )
            except Exception as e:
                logger.error(f"Meeting photo processing error: {str(e)}")

        super().save(*args, **kwargs)


class MutolaaStatSnapshot(models.Model):
    """Mutolaa API dan olingan kunlik snapshot."""
    snapshot_date = models.DateField(db_index=True)
    fetched_at = models.DateTimeField(auto_now_add=True)
    source_url = models.TextField()
    raw_payload = models.JSONField(default=dict)

    class Meta:
        ordering = ['-snapshot_date', '-fetched_at']
        verbose_name = "Mutolaa snapshot"
        verbose_name_plural = "Mutolaa snapshotlar"

    def __str__(self):
        return f"Mutolaa {self.snapshot_date}"


class MutolaaMahallaStat(models.Model):
    """Har bir mahalla bo'yicha snapshotdagi ko'rsatkichlar."""
    snapshot = models.ForeignKey(MutolaaStatSnapshot, on_delete=models.CASCADE, related_name='mahalla_stats')
    mahalla = models.ForeignKey(Mahalla, on_delete=models.SET_NULL, null=True, blank=True, related_name='mutolaa_stats')
    mahalla_external_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    mahalla_name = models.CharField(max_length=255, db_index=True)
    metrics = models.JSONField(default=dict)

    class Meta:
        ordering = ['mahalla_name']
        verbose_name = "Mutolaa mahalla statistikasi"
        verbose_name_plural = "Mutolaa mahalla statistikasi"


class MutolaaMahallaAlias(models.Model):
    """Mutolaa API dan kelgan mahalla nomini core.Mahalla bilan qo'lda moslash."""
    api_name = models.CharField(max_length=255)
    api_norm = models.CharField(max_length=255, unique=True, db_index=True)
    mahalla = models.ForeignKey(Mahalla, on_delete=models.SET_NULL, null=True, blank=True, related_name='mutolaa_aliases')
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['api_name']
        verbose_name = "Mutolaa mahalla moslash"
        verbose_name_plural = "Mutolaa mahalla moslash"

    def __str__(self):
        return f"{self.api_name} -> {self.mahalla or '-'}"


class UstozAiStatSnapshot(models.Model):
    """Ustoz AI API dan olingan kunlik snapshot."""
    snapshot_date = models.DateField(db_index=True)
    fetched_at = models.DateTimeField(auto_now_add=True)
    source_url = models.TextField()
    raw_payload = models.JSONField(default=dict)

    class Meta:
        ordering = ['-snapshot_date', '-fetched_at']
        verbose_name = "Ustoz AI snapshot"
        verbose_name_plural = "Ustoz AI snapshotlar"

    def __str__(self):
        return f"Ustoz AI {self.snapshot_date}"


class UstozAiMahallaStat(models.Model):
    """Har bir mahalla bo'yicha Ustoz AI ko'rsatkichlari."""
    snapshot = models.ForeignKey(UstozAiStatSnapshot, on_delete=models.CASCADE, related_name='area_stats')
    mahalla = models.ForeignKey(Mahalla, on_delete=models.SET_NULL, null=True, blank=True, related_name='ustoz_ai_stats')
    area_external_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    area_name = models.CharField(max_length=255, db_index=True)
    metrics = models.JSONField(default=dict)

    class Meta:
        ordering = ['area_name']
        verbose_name = "Ustoz AI mahalla statistikasi"
        verbose_name_plural = "Ustoz AI mahalla statistikasi"


class UstozAiMahallaAlias(models.Model):
    """Ustoz AI API dan kelgan mahalla nomini core.Mahalla bilan qo'lda moslash."""
    api_name = models.CharField(max_length=255)
    api_norm = models.CharField(max_length=255, unique=True, db_index=True)
    mahalla = models.ForeignKey(Mahalla, on_delete=models.SET_NULL, null=True, blank=True, related_name='ustoz_ai_aliases')
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['api_name']
        verbose_name = "Ustoz AI mahalla moslash"
        verbose_name_plural = "Ustoz AI mahalla moslash"

    def __str__(self):
        return f"{self.api_name} -> {self.mahalla or '-'}"


class UzchessStatSnapshot(models.Model):
    """UzChess API (xlsx) dan olingan kunlik snapshot."""
    snapshot_date = models.DateField(db_index=True)
    fetched_at = models.DateTimeField(auto_now_add=True)
    source_url = models.TextField()
    raw_payload = models.JSONField(default=dict)

    class Meta:
        ordering = ['-snapshot_date', '-fetched_at']
        verbose_name = "UzChess snapshot"
        verbose_name_plural = "UzChess snapshotlar"

    def __str__(self):
        return f"UzChess {self.snapshot_date}"


class UzchessMahallaStat(models.Model):
    """Har bir mahalla bo'yicha UzChess ko'rsatkichlari."""
    snapshot = models.ForeignKey(UzchessStatSnapshot, on_delete=models.CASCADE, related_name='area_stats')
    mahalla = models.ForeignKey(Mahalla, on_delete=models.SET_NULL, null=True, blank=True, related_name='uzchess_stats')
    area_external_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    area_name = models.CharField(max_length=255, db_index=True)
    metrics = models.JSONField(default=dict)

    class Meta:
        ordering = ['area_name']
        verbose_name = "UzChess mahalla statistikasi"
        verbose_name_plural = "UzChess mahalla statistikasi"


class UzchessMahallaAlias(models.Model):
    """UzChess API dan kelgan mahalla nomini core.Mahalla bilan qo'lda moslash."""
    api_name = models.CharField(max_length=255)
    api_norm = models.CharField(max_length=255, unique=True, db_index=True)
    mahalla = models.ForeignKey(Mahalla, on_delete=models.SET_NULL, null=True, blank=True, related_name='uzchess_aliases')
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['api_name']
        verbose_name = "UzChess mahalla moslash"
        verbose_name_plural = "UzChess mahalla moslash"

    def __str__(self):
        return f"{self.api_name} -> {self.mahalla or '-'}"


class QizlarAkademiyasiStatSnapshot(models.Model):
    """Qizlar akademiyasi API dan olingan kunlik snapshot."""
    snapshot_date = models.DateField(db_index=True)
    fetched_at = models.DateTimeField(auto_now_add=True)
    source_url = models.TextField()
    raw_payload = models.JSONField(default=dict)

    class Meta:
        ordering = ['-snapshot_date', '-fetched_at']
        verbose_name = "Qizlar akademiyasi snapshot"
        verbose_name_plural = "Qizlar akademiyasi snapshotlar"

    def __str__(self):
        return f"Qizlar akademiyasi {self.snapshot_date}"


class QizlarAkademiyasiMahallaStat(models.Model):
    """Har bir mahalla bo'yicha Qizlar akademiyasi ko'rsatkichlari."""
    snapshot = models.ForeignKey(QizlarAkademiyasiStatSnapshot, on_delete=models.CASCADE, related_name='area_stats')
    mahalla = models.ForeignKey(Mahalla, on_delete=models.SET_NULL, null=True, blank=True, related_name='qizlar_stats')
    area_external_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    area_name = models.CharField(max_length=255, db_index=True)
    metrics = models.JSONField(default=dict)

    class Meta:
        ordering = ['area_name']
        verbose_name = "Qizlar akademiyasi mahalla statistikasi"
        verbose_name_plural = "Qizlar akademiyasi mahalla statistikasi"


class QizlarAkademiyasiMahallaAlias(models.Model):
    """Qizlar akademiyasi API dan kelgan mahalla nomini core.Mahalla bilan qo'lda moslash."""
    api_name = models.CharField(max_length=255)
    api_norm = models.CharField(max_length=255, unique=True, db_index=True)
    mahalla = models.ForeignKey(Mahalla, on_delete=models.SET_NULL, null=True, blank=True, related_name='qizlar_aliases')
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['api_name']
        verbose_name = "Qizlar akademiyasi mahalla moslash"
        verbose_name_plural = "Qizlar akademiyasi mahalla moslash"

    def __str__(self):
        return f"{self.api_name} -> {self.mahalla or '-'}"
