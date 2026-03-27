from django import forms
from .models import OtaliqYouth, OtaliqLeader, OtaliqMeeting, OtaliqAssistance
from core.models import Yosh

class OtaliqYouthForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and not getattr(user, 'is_site_admin', False) and user.mahalla:
            self.fields['yosh'].queryset = Yosh.objects.filter(mahalla=user.mahalla)

    class Meta:
        model = OtaliqYouth
        fields = ['yosh', 'category', 'leader']
        widgets = {
            'yosh': forms.Select(attrs={'class': 'form-select select2'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'leader': forms.Select(attrs={'class': 'form-select select2'}),
        }

class OtaliqMeetingForm(forms.ModelForm):
    class Meta:
        model = OtaliqMeeting
        fields = ['meeting_date', 'photo', 'description']
        widgets = {
            'meeting_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class OtaliqAssistanceForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        provided = cleaned_data.get('provided')
        document = cleaned_data.get('document')
        existing_document = getattr(self.instance, 'document', None) if self.instance else None

        if provided and not document and not existing_document:
            self.add_error('document', "Yordam ko'rsatilgan deb belgilaganda tasdiqlovchi hujjat yuklang.")

        return cleaned_data

    class Meta:
        model = OtaliqAssistance
        fields = ['provided', 'assistance_type', 'date_provided', 'description', 'document']
        widgets = {
            'provided': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'assistance_type': forms.Select(attrs={'class': 'form-select'}),
            'date_provided': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'document': forms.FileInput(attrs={'class': 'form-control'}),
        }

class OtaliqLeaderForm(forms.ModelForm):
    class Meta:
        model = OtaliqLeader
        fields = '__all__'
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
            'organization_type': forms.Select(attrs={'class': 'form-select'}),
            'organization_name': forms.TextInput(attrs={'class': 'form-control'}),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'sector': forms.TextInput(attrs={'class': 'form-control'}),
        }
