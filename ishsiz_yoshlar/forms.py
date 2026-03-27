from django import forms
from .models import UnemployedYouth, ResponsibleLeader, YouthMeeting, AssistanceInfo, Task, TaskResponse
from core.models import Yosh, User

class UnemployedYouthForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        is_admin = bool(user and getattr(user, 'is_site_admin', False))
        mahalla_id = getattr(getattr(user, 'mahalla', None), 'id', None)

        base_queryset = Yosh.objects.all()
        if user and (not is_admin) and mahalla_id:
            base_queryset = base_queryset.filter(mahalla_id=mahalla_id)

        # Avoid rendering huge <select> options on create page.
        if self.instance and self.instance.pk:
            self.fields['yosh'].queryset = base_queryset
            return

        if self.is_bound:
            posted_yosh_id = self.data.get(self.add_prefix('yosh'))
            if posted_yosh_id and str(posted_yosh_id).isdigit():
                self.fields['yosh'].queryset = base_queryset.filter(pk=int(posted_yosh_id))
            else:
                self.fields['yosh'].queryset = Yosh.objects.none()
        else:
            self.fields['yosh'].queryset = Yosh.objects.none()

    class Meta:
        model = UnemployedYouth
        fields = ['yosh', 'category', 'leader']
        widgets = {
            'yosh': forms.Select(attrs={'class': 'form-select js-yosh-autocomplete'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'leader': forms.Select(attrs={'class': 'form-select select2'}),
        }

class MeetingForm(forms.ModelForm):
    class Meta:
        model = YouthMeeting
        fields = ['meeting_date', 'photo', 'description']
        widgets = {
            'meeting_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class AssistanceForm(forms.ModelForm):
    class Meta:
        model = AssistanceInfo
        fields = ['provided', 'assistance_type', 'date_provided', 'document']
        widgets = {
            'provided': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'assistance_type': forms.Select(attrs={'class': 'form-select'}),
            'date_provided': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'document': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned = super().clean()
        provided = cleaned.get('provided')
        assistance_type = cleaned.get('assistance_type')
        document = cleaned.get('document')
        if provided and not assistance_type:
            self.add_error('assistance_type', "Yordam turi tanlanishi shart.")
        if provided and not document:
            self.add_error('document', "Tasdiqlovchi hujjat yuklanishi shart.")
        if not provided:
            cleaned['assistance_type'] = None
        return cleaned


# Task Management Forms (Topshiriq Tizimi)

class TaskForm(forms.ModelForm):
    send_all_coordinators = forms.BooleanField(
        required=False,
        label="Barcha koordinatorlar",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    send_all_leaders = forms.BooleanField(
        required=False,
        label="Barcha yetakchilar",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    send_sector_1_coordinator = forms.BooleanField(
        required=False,
        label="1-sektor koordinatori",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    send_sector_1_leaders = forms.BooleanField(
        required=False,
        label="1-sektor yetakchilari",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    send_sector_2_coordinator = forms.BooleanField(
        required=False,
        label="2-sektor koordinatori",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    send_sector_2_leaders = forms.BooleanField(
        required=False,
        label="2-sektor yetakchilari",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    send_sector_3_coordinator = forms.BooleanField(
        required=False,
        label="3-sektor koordinatori",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    send_sector_3_leaders = forms.BooleanField(
        required=False,
        label="3-sektor yetakchilari",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    send_sector_4_coordinator = forms.BooleanField(
        required=False,
        label="4-sektor koordinatori",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    send_sector_4_leaders = forms.BooleanField(
        required=False,
        label="4-sektor yetakchilari",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Alohida yetakchilar",
        widget=forms.CheckboxSelectMultiple()
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            eligible_users = User.objects.filter(is_active=True, role='YETAKCHI')
            if not getattr(user, 'is_site_admin', False) and user.mahalla:
                eligible_users = eligible_users.filter(mahalla=user.mahalla)
            self._eligible_users = eligible_users.exclude(id=user.id)
            self.fields['recipients'].queryset = self._eligible_users
            self.fields['assigned_to'].queryset = self._eligible_users
        else:
            self._eligible_users = User.objects.filter(is_active=True, role='YETAKCHI')

        # Edit mode: only single assignee
        if self.instance and self.instance.pk:
            for name in self._group_fields():
                self.fields.pop(name, None)
            self.fields.pop('recipients', None)
        else:
            # Create mode: hide single assignee field
            self.fields.pop('assigned_to', None)

    @staticmethod
    def _group_fields():
        return [
            'send_all_coordinators',
            'send_all_leaders',
            'send_sector_1_coordinator',
            'send_sector_1_leaders',
            'send_sector_2_coordinator',
            'send_sector_2_leaders',
            'send_sector_3_coordinator',
            'send_sector_3_leaders',
            'send_sector_4_coordinator',
            'send_sector_4_leaders',
        ]

    class Meta:
        model = Task
        fields = ['title', 'description', 'priority', 'assigned_to', 'due_date', 'attachment']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Topshiriq nomi'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Topshiriq tavsifi'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select select2'}),
            'due_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned = super().clean()
        # Only validate recipients on create
        if not (self.instance and self.instance.pk):
            selected_users = cleaned.get('recipients')
            group_selected = any(cleaned.get(name) for name in self._group_fields())
            if not group_selected and not selected_users:
                self.add_error('recipients', "Kamida bitta mas'ulni tanlang.")

        return cleaned


class TaskResponseForm(forms.ModelForm):
    class Meta:
        model = TaskResponse
        fields = ['response_type', 'comment', 'completion_file']
        widgets = {
            'response_type': forms.Select(attrs={'class': 'form-select'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Izoh yozing...'}),
            'completion_file': forms.FileInput(attrs={'class': 'form-control'}),
        }
