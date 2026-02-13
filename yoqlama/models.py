from django.db import models
from core.models import User


class AttendanceSession(models.Model):
    SESSION_TYPE_CHOICES = [
        ('HOKIMIYAT', 'Hokimiyatdagi majlis'),
        ('SEMINAR', 'Seminar'),
        ('RAHBAR', 'Rahbar majlisi'),
        ('YUQORI', 'Yuqori idoralar majlisi'),
        ('ZOOM', 'Zoom/Videochat majlisi'),
        ('YIGILISH', 'Yig\'ilish'),
        ('BOSHQA', 'Boshqa'),
    ]

    session_type = models.CharField(max_length=20, choices=SESSION_TYPE_CHOICES, verbose_name="Yo'qlama turi")
    reason = models.TextField(blank=True, null=True, verbose_name="Sababi/Izoh")
    session_date = models.DateTimeField(verbose_name="Sana")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='attendance_sessions', verbose_name="Yaratgan")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    class Meta:
        ordering = ['-session_date']
        verbose_name = "Yo'qlama"
        verbose_name_plural = "Yo'qlamalar"

    def __str__(self):
        return f"{self.get_session_type_display()} - {self.session_date.strftime('%Y-%m-%d')}"


class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ('ON_TIME', 'Vaqtida qatnashdi'),
        ('LATE', 'Kechikib qatnashdi'),
        ('EXCUSED', 'Sababli qatnasha olmadi'),
        ('UNEXCUSED', 'Sababsiz qatnasha olmadi'),
        ('NA', 'Tegishli emas'),
    ]

    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='records', verbose_name="Yo'qlama")
    leader = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_records', verbose_name="Yetakchi")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, blank=True, null=True, verbose_name="Holati")
    reason = models.TextField(blank=True, null=True, verbose_name="Sababi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")

    class Meta:
        unique_together = ['session', 'leader']
        ordering = ['leader__full_name']
        verbose_name = "Yo'qlama yozuvi"
        verbose_name_plural = "Yo'qlama yozuvlari"

    def __str__(self):
        return f"{self.leader.full_name} - {self.session}"
