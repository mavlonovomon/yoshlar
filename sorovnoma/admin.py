from django.contrib import admin
from .models import Survey, Question, Choice, Response, Answer

class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 1

class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1
    show_change_link = True
    fields = ('section', 'text', 'question_type', 'choices_text', 'is_required', 'show_in_list', 'order')

    class Media:
        js = ('js/survey_admin.js',)

@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'description')
    inlines = [QuestionInline]

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'survey', 'section', 'question_type', 'is_required', 'order')
    list_filter = ('survey', 'section', 'question_type', 'is_required')
    search_fields = ('text', 'section')
    inlines = [ChoiceInline]

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ('question', 'body', 'file_body')
    can_delete = False

@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ('survey', 'user', 'created_at')
    list_filter = ('survey', 'created_at')
    search_fields = ('user__username', 'survey__title')
    inlines = [AnswerInline]
    readonly_fields = ('survey', 'user', 'created_at')
