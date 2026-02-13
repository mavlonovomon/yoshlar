from django import forms
from core.models import User
from .models import DisciplineAction


class DisciplineActionForm(forms.ModelForm):
    class Meta:
        model = DisciplineAction
        fields = ['employee', 'action_type', 'action_date', 'end_date', 'status', 'resolved_date', 'reason']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'action_type': forms.Select(attrs={'class': 'form-select'}),
            'action_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'resolved_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': "Sabab yoki izoh"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = User.objects.filter(is_active=True).order_by('full_name', 'username')

    def clean(self):
        cleaned_data = super().clean()
        action_type = cleaned_data.get('action_type')
        end_date = cleaned_data.get('end_date')
        status = cleaned_data.get('status')
        resolved_date = cleaned_data.get('resolved_date')
        action_date = cleaned_data.get('action_date')

        if action_type == 'XAYFSAN' and not end_date:
            self.add_error('end_date', "Xayfsan uchun tugash sanasi majburiy.")

        if action_type != 'XAYFSAN':
            cleaned_data['end_date'] = None

        if status == 'YECHILGAN' and not resolved_date:
            self.add_error('resolved_date', "Yechilgan holat uchun sana kiriting.")

        if status == 'BOR':
            cleaned_data['resolved_date'] = None

        if action_date and resolved_date and resolved_date < action_date:
            self.add_error('resolved_date', "Yechilgan sana jazo sanasidan oldin bo'lishi mumkin emas.")

        return cleaned_data
