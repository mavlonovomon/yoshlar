from django import forms
from django.utils import timezone

from .models import Question, Subject, TestConfig


class TestConfigForm(forms.ModelForm):
    class Meta:
        model = TestConfig
        fields = [
            'title',
            'subject',
            'question_sets',
            'start_time',
            'end_time',
            'duration_minutes',
            'questions_count',
            'question_order',
            'max_attempts',
            'is_active',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Sinov nomi'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'question_sets': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 6}),
            'start_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'questions_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'question_order': forms.Select(attrs={'class': 'form-select'}),
            'max_attempts': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['subject'].required = False
        self.fields['question_sets'].required = False
        self.fields['question_sets'].queryset = Subject.objects.order_by('name')
        self.fields['question_sets'].help_text = "Bir yoki bir nechta savol to'plamini tanlang."

        if self.instance and self.instance.pk:
            if self.instance.start_time:
                self.initial['start_time'] = timezone.localtime(self.instance.start_time).strftime('%Y-%m-%dT%H:%M')
            if self.instance.end_time:
                self.initial['end_time'] = timezone.localtime(self.instance.end_time).strftime('%Y-%m-%dT%H:%M')
            if not self.initial.get('question_sets') and self.instance.subject_id:
                self.initial['question_sets'] = [self.instance.subject_id]

    def clean(self):
        cleaned_data = super().clean()
        subject = cleaned_data.get('subject')
        question_sets = cleaned_data.get('question_sets')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        questions_count = cleaned_data.get('questions_count') or 0

        selected_subject_ids = []
        if question_sets is not None and question_sets.exists():
            selected_subject_ids = list(question_sets.values_list('id', flat=True))
        elif subject:
            selected_subject_ids = [subject.id]

        if not selected_subject_ids:
            self.add_error('question_sets', "Kamida bitta savol to'plamini tanlang.")
            return cleaned_data

        available_questions_count = Question.objects.filter(subject_id__in=selected_subject_ids).count()
        if available_questions_count == 0:
            self.add_error('question_sets', "Tanlangan to'plamlarda savollar topilmadi.")
        elif questions_count > available_questions_count:
            self.add_error(
                'questions_count',
                f"Tanlangan to'plamlarda {available_questions_count} ta savol bor. "
                f"Savollar soni undan oshmasligi kerak."
            )

        if start_time and end_time and start_time >= end_time:
            self.add_error('end_time', "Tugash vaqti boshlanish vaqtidan keyin bo'lishi shart.")

        return cleaned_data
