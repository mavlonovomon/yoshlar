from django.conf import settings
from django.db import models


class DisciplineAction(models.Model):
    ACTION_CHOICES = [
        ('OGOHLANTIRISH', 'Ogohlantirish'),
        ('XAYFSAN', 'Xayfsan'),
        ('ISH_HAQI_30', 'Ish haqidan 30 foiz'),
        ('ISH_HAQI_50', 'Ish haqidan 50 foiz'),
    ]
    STATUS_CHOICES = [
        ('BOR', 'Bor'),
        ('YECHILGAN', 'Yechilgan'),
    ]

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='discipline_actions',
        verbose_name="Xodim",
    )
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Jazo turi")
    action_date = models.DateField(verbose_name="Jazo sanasi")
    end_date = models.DateField(null=True, blank=True, verbose_name="Tugash sanasi")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='BOR', verbose_name="Joriy holati")
    resolved_date = models.DateField(null=True, blank=True, verbose_name="Yechilgan sana")
    reason = models.TextField(blank=True, verbose_name="Sababi / izoh")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_discipline_actions',
        verbose_name="Kiritgan foydalanuvchi",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-action_date', '-created_at']
        verbose_name = "Intizomiy jazo"
        verbose_name_plural = "Intizomiy jazolar"

    def __str__(self):
        return f"{self.employee} - {self.get_action_type_display()} ({self.action_date})"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.action_type == 'XAYFSAN' and not self.end_date:
            raise ValidationError({'end_date': "Xayfsan uchun tugash sanasi majburiy."})

        if self.status == 'YECHILGAN' and not self.resolved_date:
            raise ValidationError({'resolved_date': "Yechilgan holat uchun yechilgan sana majburiy."})

        if self.resolved_date and self.resolved_date < self.action_date:
            raise ValidationError({'resolved_date': "Yechilgan sana jazo sanasidan oldin bo'lishi mumkin emas."})
