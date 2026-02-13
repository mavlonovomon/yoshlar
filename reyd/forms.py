from django import forms
from django.core.exceptions import ValidationError
from .models import RaidEvent, RaidPhoto
from core.models import Mahalla

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class RaidEventForm(forms.ModelForm):
    photos = MultipleFileField(
        required=False,
        label="Rasmlar (ko'pi bilan 5 ta)",
        widget=MultipleFileInput(
            attrs={'class': 'form-control', 'multiple': True, 'accept': '.jpg,.jpeg,.png,image/*'}
        ),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        self.user = user
        super().__init__(*args, **kwargs)
        if user and not getattr(user, 'is_site_admin', False) and user.mahalla:
            self.fields['mahalla'].queryset = Mahalla.objects.filter(id=user.mahalla.id)
            self.fields['mahalla'].initial = user.mahalla

    def get_new_photos(self):
        return self.cleaned_data.get('photos', [])

    def clean_mahalla(self):
        mahalla = self.cleaned_data.get('mahalla')
        if self.user and not getattr(self.user, 'is_site_admin', False) and self.user.mahalla:
            return self.user.mahalla
        return mahalla

    def clean(self):
        cleaned = super().clean()
        new_photos = self.get_new_photos()
        if not isinstance(new_photos, list):
            new_photos = [new_photos] if new_photos else []
            
        existing_photos = self.instance.photos.count() if self.instance and self.instance.pk else 0
        if existing_photos + len(new_photos) > 5:
            raise ValidationError("Ko'pi bilan 5 ta rasm yuklash mumkin.")
            
        for photo in new_photos:
            ext = photo.name.rsplit('.', 1)[-1].lower() if '.' in photo.name else ''
            if ext not in ('jpg', 'jpeg', 'png'):
                raise ValidationError(f"Rasm formati faqat JPG/JPEG/PNG bo'lishi kerak: {photo.name}")
        return cleaned

    class Meta:
        model = RaidEvent
        fields = ['title', 'mahalla', 'event_date', 'event_type', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'mahalla': forms.Select(attrs={'class': 'form-select select2'}),
            'event_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'event_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
