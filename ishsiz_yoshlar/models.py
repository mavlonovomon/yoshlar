import uuid
import logging
from PIL import Image
from io import BytesIO
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.core.files.uploadedfile import InMemoryUploadedFile
from core.models import Yosh, Mahalla

logger = logging.getLogger(__name__)


class ResponsibleLeader(models.Model):
    LEVEL_CHOICES = [
        ('TUMAN', 'Tuman darajasi'),
        ('VILOYAT', 'Viloyat darajasi'),
        ('RESPUBLIKA', 'Respublika darajasi'),
        ('OTM', 'OTM'),
    ]

    full_name = models.CharField(max_length=255, verbose_name="F.I.Sh")
    position = models.CharField(max_length=255, verbose_name="Lavozimi")
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, verbose_name="Darajasi")
    phone_number = models.CharField(max_length=20, verbose_name="Telefon raqami")
    organization = models.CharField(max_length=255, blank=True, null=True, verbose_name="Tashkilot nomi")
    sector = models.CharField(max_length=100, blank=True, null=True, verbose_name="Soha")

    class Meta:
        ordering = ['full_name']
        verbose_name = "Mas'ul rahbar"
        verbose_name_plural = "Mas'ul rahbarlar"

    def __str__(self):
        return f"{self.full_name} ({self.get_level_display()})"

class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class UnemployedYouth(models.Model):
    YEAR_CHOICES = [
        (2025, '2025'),
        (2026, '2026'),
    ]

    CATEGORY_CHOICES = [
        ('MIGRATSIYA', "Migratsiyadan qaytgan ishsizlar"),
        ('MAKTAB', 'Maktab'),
        ('KASBIY', "Kasbiy ta'lim"),
        ('OLIY', "Oliy ta'lim"),
        ('QOLGAN', 'Qolgan ishsizlar'),
    ]

    yosh = models.OneToOneField(Yosh, on_delete=models.CASCADE, related_name='unemployed_profile', verbose_name="Yosh")
    year = models.PositiveSmallIntegerField(choices=YEAR_CHOICES, default=2025, verbose_name="Yil", db_index=True)
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, verbose_name="Toifa", db_index=True)
    leader = models.ForeignKey(ResponsibleLeader, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_youths', verbose_name="Mas'ul rahbar")
    otm_name = models.CharField(max_length=500, blank=True, default='', verbose_name="Ta'lim tashkiloti")
    direction = models.CharField(max_length=500, blank=True, default='', verbose_name="Yo'nalish")

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Qo'shilgan vaqti")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Tahrirlangan vaqti")
    is_deleted = models.BooleanField(default=False, verbose_name="O'chirilgan", db_index=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    def delete(self, **kwargs):
        self.is_deleted = True
        self.save()

    class Meta:
        verbose_name = "Ishsiz yosh"
        verbose_name_plural = "Ishsiz yoshlar"
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['leader']),
            models.Index(fields=['year']),
        ]

    def __str__(self):
        return self.yosh.fullname

class YouthMeeting(models.Model):
    unemployed_youth = models.ForeignKey(UnemployedYouth, on_delete=models.CASCADE, related_name='meetings', verbose_name="Ishsiz yosh")
    meeting_date = models.DateTimeField(verbose_name="Uchrashuv vaqti")
    photo = models.ImageField(upload_to='meetings/', verbose_name="Uchrashuv rasmi", validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])])
    description = models.TextField(verbose_name="Uchrashuv mazmuni/izoh")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Uchrashuv"
        verbose_name_plural = "Uchrashuvlar"
        ordering = ['-meeting_date']

class AssistanceInfo(models.Model):
    ASSISTANCE_TYPES = [
        ('ISH', 'Doimiy ishga joylashgan'),
        ('KREDIT', 'Tadbirkorlik uchun kredit ajratilgan'),
        ('MIGRATSIYA', 'Tartibli migratsiyaga yuborilgan'),
        ('YER', 'Ekin yer maydoni ajratilgan'),
        ('SUBSIDIYA', 'Asbob-uskuna ajratilgan'),
    ]

    unemployed_youth = models.OneToOneField(UnemployedYouth, on_delete=models.CASCADE, related_name='assistance', verbose_name="Ishsiz yosh")
    provided = models.BooleanField(default=False, verbose_name="Yordam ko'rsatilgan")
    assistance_type = models.CharField(max_length=50, choices=ASSISTANCE_TYPES, blank=True, null=True, verbose_name="Yordam yo'nalishi")
    date_provided = models.DateField(blank=True, null=True, verbose_name="Yordam ko'rsatilgan sana")
    document = models.FileField(upload_to='assistance_docs/', blank=True, null=True, verbose_name="Tasdiqlovchi hujjat", validators=[FileExtensionValidator(['pdf', 'zip', 'rar'])])
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Yordam ma'lumoti"
        verbose_name_plural = "Yordam ma'lumotlari"

    def clean(self):
        super().clean()
        if self.provided and not self.assistance_type:
            raise ValidationError({"assistance_type": "Yordam turi tanlanishi shart."})
        if self.provided and not self.document:
            raise ValidationError({"document": "Tasdiqlovchi hujjat yuklanishi shart."})
        if not self.provided:
            self.assistance_type = None


# Task Group (Topshiriq umumiy ma'lumotlari)
class TaskGroup(models.Model):
    PRIORITY_CHOICES = [
        ('LOW', 'Past'),
        ('MEDIUM', "O'rta"),
        ('HIGH', 'Yuqori'),
        ('URGENT', 'Shoshilinch'),
    ]

    title = models.CharField(max_length=255, verbose_name="Topshiriq nomi")
    description = models.TextField(verbose_name="Topshiriq tavsifi")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM', verbose_name="Muhimlik")

    created_by = models.ForeignKey(
        'core.User',
        on_delete=models.CASCADE,
        related_name='created_task_groups',
        verbose_name="Yaratgan admin"
    )

    target_youth = models.ForeignKey(
        Yosh,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='task_groups',
        verbose_name="Mo'ljaldagi yosh"
    )
    target_mahalla = models.ForeignKey(
        Mahalla,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='task_groups',
        verbose_name="Mo'ljaldagi mahalla"
    )

    due_date = models.DateTimeField(verbose_name="Bajarish muddati")
    attachment = models.FileField(
        upload_to='task_attachments/',
        null=True,
        blank=True,
        verbose_name="Biriktirilgan fayl",
        validators=[FileExtensionValidator(['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png', 'zip'])]
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Topshiriq guruhi"
        verbose_name_plural = "Topshiriq guruhlari"

    def __str__(self):
        return self.title


# Task Management System (Topshiriq Tizimi)
class Task(models.Model):
    STATUS_CHOICES = [
        ('YANGI', 'Yangi'),
        ('BAJARILMOQDA', 'Bajarilmoqda'),
        ('TASDIQLANGAN', 'Tekshirilmoqda'),
        ('RAD_ETILGAN', 'Rad etilgan'),
        ('YAKUNLANGAN', 'Yakunlangan'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Past'),
        ('MEDIUM', "O'rta"),
        ('HIGH', 'Yuqori'),
        ('URGENT', 'Shoshilinch'),
    ]

    title = models.CharField(max_length=255, verbose_name="Topshiriq nomi")
    description = models.TextField(verbose_name="Topshiriq tavsifi")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='YANGI', verbose_name="Holati")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM', verbose_name="Muhimlik")
    task_group = models.ForeignKey(
        TaskGroup,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='assignments',
        verbose_name="Topshiriq guruhi"
    )
    
    # Assignment
    assigned_to = models.ForeignKey(
        'core.User', 
        on_delete=models.CASCADE, 
        related_name='assigned_tasks',
        verbose_name="Ijro uchun topshirilgan"
    )
    created_by = models.ForeignKey(
        'core.User', 
        on_delete=models.CASCADE, 
        related_name='created_tasks',
        verbose_name="Yaratgan admin"
    )
    
    # Target youth (optional - can be assigned to a specific youth or general)
    target_youth = models.ForeignKey(
        Yosh, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='tasks',
        verbose_name="Mo'ljaldagi yosh"
    )
    target_mahalla = models.ForeignKey(
        Mahalla, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='tasks',
        verbose_name="Mo'ljaldagi mahalla"
    )
    
    # Deadlines
    due_date = models.DateTimeField(verbose_name="Bajarish muddati")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Bajarilgan vaqt")
    
    # Files
    attachment = models.FileField(
        upload_to='task_attachments/', 
        null=True, 
        blank=True,
        verbose_name="Biriktirilgan fayl",
        validators=[FileExtensionValidator(['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png', 'zip'])]
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")
    batch_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Topshiriq"
        verbose_name_plural = "Topshiriqlar"
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['due_date']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['task_group']),
        ]

    def __str__(self):
        return f"{self.title} - {self.assigned_to.full_name}"

    @property
    def progress_percent(self) -> int:
        """Topshiriq holatiga qarab bajarilish foizi."""
        return 100 if self.status == 'YAKUNLANGAN' else 0


class TaskResponse(models.Model):
    RESPONSE_CHOICES = [
        ('QABUL_QILDIM', 'Qabul qildim'),
        ('RAD_ETDIM', 'Rad etdim'),
        ('BAJARILDI', 'Bajarildi'),
        ('MUAMMO_BOR', 'Muamm bor'),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='responses', verbose_name="Topshiriq")
    user = models.ForeignKey('core.User', on_delete=models.CASCADE, related_name='task_responses', verbose_name="Foydalanuvchi")
    
    response_type = models.CharField(max_length=20, choices=RESPONSE_CHOICES, verbose_name="Javob turi")
    comment = models.TextField(blank=True, null=True, verbose_name="Izoh")
    
    # Completion files
    completion_file = models.FileField(
        upload_to='task_completions/', 
        null=True, 
        blank=True,
        verbose_name="Bajarilgan ishing fayli",
        validators=[FileExtensionValidator(['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png', 'zip'])]
    )
    
    responded_at = models.DateTimeField(auto_now_add=True, verbose_name="Javob berilgan vaqt")
    
    class Meta:
        ordering = ['-responded_at']
        verbose_name = "Topshiriq javobi"
        verbose_name_plural = "Topshiriq javoblari"
        unique_together = ['task', 'user']

    def __str__(self):
        return f"{self.user.full_name} - {self.task.title} - {self.get_response_type_display()}"


class TaskNotification(models.Model):
    NOTIFICATION_TYPES = [
        ('TASK_CREATED', 'Topshiriq yaratildi'),
        ('TASK_UPDATED', 'Topshiriq yangilandi'),
        ('TASK_RESPONSE', 'Javob qabul qilindi'),
        ('TASK_COMPLETED', 'Topshiriq yakunlandi'),
        ('TASK_OVERDUE', 'Topshiriq muddati o\'tgan'),
        ('TASK_RETURNED', 'Topshiriq qaytarildi'),
        ('TASK_APPROVED', 'Topshiriq tasdiqlandi'),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='notifications', verbose_name="Topshiriq")
    recipient = models.ForeignKey('core.User', on_delete=models.CASCADE, related_name='task_notifications', verbose_name="Qabul qiluvchi")
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, verbose_name="Xabar turi")
    
    message = models.TextField(verbose_name="Xabar matni")
    is_read = models.BooleanField(default=False, verbose_name="O'qilgan")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Topshiriq xabari"
        verbose_name_plural = "Topshiriq xabarlari"
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self):
        return f"{self.notification_type} - {self.recipient.full_name}"
