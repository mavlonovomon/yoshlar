from django.db import models
from django.utils import timezone


class SolarPanel(models.Model):
    mahalla = models.OneToOneField(
        "core.Mahalla",
        on_delete=models.CASCADE,
        related_name="solar_panel",
        verbose_name="Mahalla",
    )
    is_installed = models.BooleanField(default=False, verbose_name="O'rnatilgan")
    capacity_kw = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Quvvat (kVt)"
    )
    installed_date = models.DateField(null=True, blank=True, verbose_name="O'rnatilgan sana")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")
    updated_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Yangilagan foydalanuvchi",
    )

    class Meta:
        ordering = ["mahalla__name"]
        verbose_name = "Quyosh paneli"
        verbose_name_plural = "Quyosh panellari"

    def __str__(self):
        status = "O'rnatilgan" if self.is_installed else "O'natmagan"
        return f"{self.mahalla.name} — {status}"
