from django import forms
from django.core.exceptions import ValidationError
from .models import FiveInitiativeEvent, FiveInitiativePhoto
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


class FiveInitiativeEventForm(forms.ModelForm):
    TITLE_OPTIONS = {
        'SPORT': [
            "Voleybol", "Shaxmat", "Workout", "Stol tennisi", "Yengil atletika",
            "Gimnastrada", "Stribol", "Sashka", "Milliy kurash", "Futbol",
            "Mini futbol", "Armrestling", "Gandbol",
        ],
        'KASB': [
            "Dizaynerlik (Liboslar bo'yicha)", "Sartaroshlik", "Novvoychilik",
            "Payvandlash ustasi", "Elektr montaj ustasi",
        ],
        'SANAT': [
            "Yosh musavvir", "Mohir fortepianochi", "Yoshlar ovozi",
        ],
        'KIBER': [
            "Valorant (PC)", "CS2 (PC)", "DOTA 2 (PC)", "eFootball 2024 (PS)",
        ],
        'INTEL': [
            "Zakovat intellektual o'yini",
        ],
        'KITOB': [
            "Yosh kitobxon oila", "Yosh kitobxon tanlovi",
        ],
    }

    photos = MultipleFileField(
        required=False,
        label="Rasmlar (ko'pi bilan 3 ta)",
        widget=MultipleFileInput(
            attrs={'class': 'form-control', 'multiple': True, 'accept': '.jpg,.jpeg,.png,image/*'}
        ),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['title'].widget = forms.Select(attrs={'class': 'form-select'})
        self.fields['title'].choices = self._title_choices_for_direction(
            self._selected_direction(),
            self._selected_title(),
        )
        if user and not getattr(user, 'is_site_admin', False) and user.mahalla:
            self.fields['mahalla'].queryset = Mahalla.objects.filter(id=user.mahalla.id)
            self.fields['mahalla'].initial = user.mahalla
            # Instead of readonly, we can use a widget that doesn't allow changes but sends the value
            # or just rely on the queryset being limited to one.
            # To be safe, we also force it in clean_mahalla

    @classmethod
    def get_title_options(cls):
        return cls.TITLE_OPTIONS

    def _selected_direction(self):
        if self.is_bound:
            return self.data.get('direction')
        if self.instance and self.instance.pk:
            return self.instance.direction
        return None

    def _title_choices_for_direction(self, direction, current_title=None):
        options = self.TITLE_OPTIONS.get(direction, [])
        if current_title is None:
            current_title = self._selected_title()
        if current_title and current_title not in options:
            options = [current_title] + options
        choices = [('', "Tadbir nomini tanlang")]
        choices.extend([(item, item) for item in options])
        return choices

    def _selected_title(self):
        if self.is_bound:
            return self.data.get('title')
        if self.instance and self.instance.pk:
            return self.instance.title
        return None

    def get_new_photos(self):
        return self.cleaned_data.get('photos', [])

    def clean_mahalla(self):
        mahalla = self.cleaned_data.get('mahalla')
        # If leader, force their mahalla
        from core.models import User
        user = getattr(self, 'user', None)
        if user and not getattr(user, 'is_site_admin', False) and user.mahalla:
            return user.mahalla
        return mahalla

    def clean(self):
        cleaned = super().clean()
        direction = cleaned.get('direction')
        title = cleaned.get('title')
        
        if direction and title:
            allowed_titles = self.TITLE_OPTIONS.get(direction, [])
            if title not in allowed_titles:
                self.add_error('title', "Tanlangan yo'nalishga mos tadbir nomini tanlang.")

        new_photos = self.get_new_photos()
        if not isinstance(new_photos, list):
            new_photos = [new_photos] if new_photos else []
            
        existing_photos = self.instance.photos.count() if self.instance and self.instance.pk else 0
        if existing_photos + len(new_photos) > 3:
            raise ValidationError("Ko'pi bilan 3 ta rasm yuklash mumkin.")
            
        for photo in new_photos:
            ext = photo.name.rsplit('.', 1)[-1].lower() if '.' in photo.name else ''
            if ext not in ('jpg', 'jpeg', 'png'):
                raise ValidationError(f"Rasm formati faqat JPG/JPEG/PNG bo'lishi kerak: {photo.name}")
        return cleaned

    class Meta:
        model = FiveInitiativeEvent
        fields = ['direction', 'title', 'event_date', 'mahalla', 'coverage', 'description']
        widgets = {
            'direction': forms.Select(attrs={'class': 'form-select'}),
            'event_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'mahalla': forms.Select(attrs={'class': 'form-select select2'}),
            'coverage': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'step': '1'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class FiveInitiativePhotoForm(forms.ModelForm):
    class Meta:
        model = FiveInitiativePhoto
        fields = ['image']
