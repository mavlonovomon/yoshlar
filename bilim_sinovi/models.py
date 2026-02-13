from django.db import models
from core.models import User
import os

class Subject(models.Model):
    name = models.CharField(max_length=200, verbose_name="Fan/Yo'nalish")
    description = models.TextField(blank=True, verbose_name="Ta'rif")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Fan"
        verbose_name_plural = "Fanlar"

class TestConfig(models.Model):
    QUESTION_ORDER_CHOICES = [
        ('RANDOM', "Aralash"),
        ('SEQUENTIAL', "Tartib bilan"),
    ]

    title = models.CharField(max_length=255, verbose_name="Sinov nomi")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Fan", null=True, blank=True)
    question_sets = models.ManyToManyField(
        Subject,
        blank=True,
        related_name='test_configs',
        verbose_name="Savollar to'plami",
    )
    start_time = models.DateTimeField(verbose_name="Boshlanish vaqti")
    end_time = models.DateTimeField(verbose_name="Tugash vaqti")
    duration_minutes = models.PositiveIntegerField(verbose_name="Davomiyligi (daqiqa)")
    questions_count = models.PositiveIntegerField(default=10, verbose_name="Savollar soni")
    question_order = models.CharField(
        max_length=20,
        choices=QUESTION_ORDER_CHOICES,
        default='RANDOM',
        verbose_name="Savol tartibi",
    )
    max_attempts = models.PositiveIntegerField(default=1, verbose_name="Maksimal urinishlar soni")
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def get_effective_subject_ids(self):
        subject_ids = list(self.question_sets.values_list('id', flat=True))
        if subject_ids:
            return subject_ids
        if self.subject_id:
            return [self.subject_id]
        return []

    def available_questions_count(self):
        subject_ids = self.get_effective_subject_ids()
        if not subject_ids:
            return 0
        return Question.objects.filter(subject_id__in=subject_ids).count()

    class Meta:
        verbose_name = "Sinov Sozlamasi"
        verbose_name_plural = "Sinov Sozlamalari"
        ordering = ['-start_time']

class Question(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='questions', verbose_name="Fan")
    text = models.TextField(verbose_name="Savol matni")
    option_a = models.CharField(max_length=500, verbose_name="Variant A")
    option_b = models.CharField(max_length=500, verbose_name="Variant B")
    option_c = models.CharField(max_length=500, verbose_name="Variant C")
    option_d = models.CharField(max_length=500, verbose_name="Variant D")
    correct_answer = models.CharField(
        max_length=1, 
        choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')],
        verbose_name="To'g'ri javob"
    )
    file_source = models.CharField(max_length=255, blank=True, null=True, verbose_name="Manba fayl")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subject} - {self.text[:50]}"

    class Meta:
        verbose_name = "Savol"
        verbose_name_plural = "Savollar"

class TestResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='test_results', verbose_name="Foydalanuvchi")
    test_config = models.ForeignKey(TestConfig, on_delete=models.CASCADE, related_name='results', verbose_name="Sinov")
    score = models.PositiveIntegerField(default=0, verbose_name="Ball")
    correct_answers_count = models.PositiveIntegerField(default=0, verbose_name="To'g'ri javoblar")
    total_questions = models.PositiveIntegerField(default=0, verbose_name="Jami savollar")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Boshlangan vaqti")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Tugagan vaqti")
    data = models.JSONField(default=dict, blank=True, verbose_name="Javoblar tarixi") # Store which questions were asked and answers given

    def __str__(self):
        return f"{self.user.full_name} - {self.test_config.title} - {self.score}"

    class Meta:
        verbose_name = "Natija"
        verbose_name_plural = "Natijalar"
