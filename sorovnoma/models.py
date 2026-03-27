from django.db import models
from django.conf import settings

class SurveyStatus(models.TextChoices):
    ACTIVE = 'active', "Aktiv"
    PAUSED = 'paused', "To'xtatilgan"
    COMPLETED = 'completed', "Tugallangan"

class Survey(models.Model):
    title = models.CharField(max_length=255, verbose_name="Nomi")
    description = models.TextField(blank=True, null=True, verbose_name="Ta'rifi")
    status = models.CharField(max_length=20, choices=SurveyStatus.choices, default=SurveyStatus.ACTIVE, verbose_name="Holati")
    allow_multi = models.BooleanField(default=False, verbose_name="Qayta to'ldirish", help_text="Belgilansa tahrirlash emas yangidan javob yaratish mumkin bo'ladi.")
    allow_edit = models.BooleanField(default=False, verbose_name="Javobni tahrirlash", help_text="Tahrirlash imkoni")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "So'rovnoma"
        verbose_name_plural = "So'rovnomalar"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

class QuestionType(models.TextChoices):
    SHORT_TEXT = 'short_text', "Qisqa matn (text)"
    LONG_TEXT = 'long_text', "Uzun matn (textarea)"
    NUMBER = 'number', "Son (number)"
    DATE = 'date', "Sana (date)"
    RADIO = 'radio', "Radio tugma (bitta tanlov)"
    CHECKBOX = 'checkbox', "Checkbox (ko'p tanlov)"
    SELECT = 'select', "Ochiluvchi ro'yxat (select)"
    BUTTONS = 'buttons', "Tanlanadigan tugmalar"
    IMAGE = 'image', "Rasm (image)"
    FILE = 'file', "Fayl (file)"

class Question(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='questions', verbose_name="So'rovnoma")
    section = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Bo'lim",
        help_text="Bir xil bo'lim nomini yozsangiz savollar guruhlanadi.",
    )
    text = models.CharField(max_length=500, verbose_name="Savol matni")
    question_type = models.CharField(max_length=20, choices=QuestionType.choices, verbose_name="Savol turi")
    is_required = models.BooleanField(default=True, verbose_name="Majburiymi?")
    choices_text = models.TextField(blank=True, null=True, verbose_name="Variantlar", help_text="Faqat tanlovli savollar uchun. Har bir variantni yangi qatordan yozing (Enter bosib).")
    show_in_list = models.BooleanField(default=False, verbose_name="Natijalar ro'yxatida ustun sifatida ko'rsatish", help_text="Belgilansa, ushbu savol javobi 'Barcha natijalar' jadvalida alohida ustun bo'lib chiqadi.")
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib raqami")

    class Meta:
        verbose_name = "Savol"
        verbose_name_plural = "Savollar"
        ordering = ['order']

    def __str__(self):
        return self.text

    def get_choices_list(self):
        if self.choices_text:
            return [x.strip() for x in self.choices_text.split('\n') if x.strip()]
        return []

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices', verbose_name="Savol")
    text = models.CharField(max_length=255, verbose_name="Variant matni")
    order = models.PositiveIntegerField(default=0, verbose_name="Tartib raqami")

    class Meta:
        verbose_name = "Variant"
        verbose_name_plural = "Variantlar"
        ordering = ['order']

    def __str__(self):
        return f"{self.question} - {self.text}"

class Response(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='responses', verbose_name="So'rovnoma")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True, verbose_name="Foydalanuvchi")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Kiritilgan vaqt")

    class Meta:
        verbose_name = "Javob (So'rovnoma natijasi)"
        verbose_name_plural = "Javoblar (So'rovnoma natijalari)"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.survey.title} - {self.user}"

class Answer(models.Model):
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name='answers', verbose_name="So'rovnoma natijasi")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers', verbose_name="Savol")
    body = models.TextField(blank=True, null=True, verbose_name="Matnli javob")
    file_body = models.FileField(upload_to='survey_files/', blank=True, null=True, verbose_name="Fayl/Rasm javob")

    class Meta:
        verbose_name = "Savolga javob"
        verbose_name_plural = "Savollarga javoblar"

    def __str__(self):
        return f"{self.question} - {self.response}"
