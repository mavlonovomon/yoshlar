from django.db import models
from django.core.validators import FileExtensionValidator
from django.core.files.uploadedfile import InMemoryUploadedFile
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
