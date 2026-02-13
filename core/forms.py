from django import forms
from .models import Yosh, Uchrashuv, Mahalla, User
from collections import OrderedDict

class MahallaLoginForm(forms.Form):
    mahalla = forms.ModelChoiceField(
        queryset=Mahalla.objects.all(),
        empty_label="Mahallani tanlang...",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    username = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Admin/Rahbar logini'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Parol'})
    )

class YoshForm(forms.ModelForm):
    conversation_text = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        required=False,
        label="Suhbat mazmuni"
    )
    conversation_photo = forms.ImageField(
        required=False,
        label="Suhbat rasmi",
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and getattr(user, 'is_site_admin', False):
            self.fields['mahalla'] = forms.ModelChoiceField(
                queryset=Mahalla.objects.all(),
                widget=forms.Select(attrs={'class': 'form-control select2'}),
                label="Mahalla",
                required=True
            )
            # Reorder fields to put mahalla after fullname
            keys = list(self.fields.keys())
            if 'mahalla' in keys and 'fullname' in keys:
                keys.remove('mahalla')
                idx = keys.index('fullname') + 1
                keys.insert(idx, 'mahalla')
                self.fields = OrderedDict((k, self.fields[k]) for k in keys)
        
        # If edit mode, mahalla might already be on the instance
        if self.instance and self.instance.pk and 'mahalla' in self.fields:
            self.initial['mahalla'] = self.instance.mahalla

    class Meta:
        model = Yosh
        fields = ['fullname', 'birth_date', 'passport_number', 'jshshir', 'address', 'photo', 'phone_number']
        widgets = {
            'fullname': forms.TextInput(attrs={'class': 'form-control'}),
            'birth_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'passport_number': forms.TextInput(attrs={'class': 'form-control'}),
            'jshshir': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

class UchrashuvForm(forms.ModelForm):
    class Meta:
        model = Uchrashuv
        fields = ['meeting_date', 'conversation_text', 'photo']
        widgets = {
            'meeting_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'conversation_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
        }


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            'full_name',
            'profile_image',
            'pinfl',
            'phone_number',
            'email',
            'telegram_username',
            'birth_date',
            'position',
            'address',
            'education',
            'specialization',
            'work_start_date',
            'emergency_contact',
            'about',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_image': forms.FileInput(attrs={'class': 'form-control'}),
            'pinfl': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telegram_username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '@username'}),
            'birth_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'education': forms.TextInput(attrs={'class': 'form-control'}),
            'specialization': forms.TextInput(attrs={'class': 'form-control'}),
            'work_start_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'emergency_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'about': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
