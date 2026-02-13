from django.db import models
from django.core.validators import FileExtensionValidator
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image
from io import BytesIO
import logging
from core.models import Mahalla

logger = logging.getLogger(__name__)


class RaidEvent(models.Model):
    TYPE_CHOICES = [
        ('TIG', "Tig' reydi"),
        ('TUNGI', 'Tungi reyd'),
        ('BOSHQA', 'Boshqa reyd'),
    ]

    title = models.CharField(max_length=255, verbose_name="Tadbir nomi")
    mahalla = models.ForeignKey(Mahalla, on_delete=models.CASCADE, related_name='reyd_events', verbose_name="Mahalla")
    event_date = models.DateField(verbose_name="Sana")
    event_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='BOSHQA', verbose_name="Reyd turi")
    description = models.TextField(blank=True, null=True, verbose_name="Izoh")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Qo'shilgan vaqti")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Tahrirlangan vaqti")

    class Meta:
        ordering = ['-event_date', '-created_at']
        verbose_name = "Reyd tadbiri"
        verbose_name_plural = "Reyd tadbirlari"

    def __str__(self):
        return f"{self.title} - {self.mahalla.name}"


class RaidPhoto(models.Model):
    event = models.ForeignKey(RaidEvent, on_delete=models.CASCADE, related_name='photos', verbose_name="Reyd tadbiri")
    image = models.ImageField(
        upload_to='reyd/photos/',
        verbose_name="Rasm",
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Reyd rasmi"
        verbose_name_plural = "Reyd rasmlari"

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
                logger.error("Reyd photo processing error: %s", exc)

        super().save(*args, **kwargs)
