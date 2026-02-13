from django.db import models
from django.conf import settings


class EimzoProfile(models.Model):
    """E-IMZO sertifikat meta-ma'lumotlari (ixtiyoriy)."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='eimzo_profile'
    )
    cert_serial = models.CharField(max_length=128, blank=True, null=True)
    cert_subject = models.TextField(blank=True, null=True)
    cert_valid_from = models.DateTimeField(blank=True, null=True)
    cert_valid_to = models.DateTimeField(blank=True, null=True)
    last_verified_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "E-IMZO profil"
        verbose_name_plural = "E-IMZO profillar"

    def __str__(self):
        return f"E-IMZO: {self.user}"
