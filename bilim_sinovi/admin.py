from django.contrib import admin
from .models import Subject, TestConfig, Question, TestResult


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(TestConfig)
class TestConfigAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'subject',
        'question_order',
        'start_time',
        'end_time',
        'duration_minutes',
        'questions_count',
        'max_attempts',
        'is_active',
    )
    list_filter = ('is_active', 'subject', 'question_order')
    search_fields = ('title',)
    date_hierarchy = 'start_time'
    filter_horizontal = ('question_sets',)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('subject', 'text', 'correct_answer', 'created_at')
    list_filter = ('subject',)
    search_fields = ('text', 'option_a', 'option_b', 'option_c', 'option_d')
    raw_id_fields = ('subject',)


@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'test_config', 'score', 'correct_answers_count', 'total_questions', 'started_at', 'finished_at')
    list_filter = ('test_config',)
    search_fields = ('user__full_name',)
    raw_id_fields = ('user', 'test_config')
