from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import MigrationYouth, MigrationMeeting
from core.models import Yosh

COUNTRY_CHOICES = [
    ('Rossiya', 'Rossiya'),
    ("Qozog'iston", "Qozog'iston"),
    ('Koreya Respublikasi', 'Koreya Respublikasi'),
    ('Turkiya', 'Turkiya'),
    ('Birlashgan Arab Amirliklari', 'Birlashgan Arab Amirliklari'),
    ('Saudiya Arabistoni', 'Saudiya Arabistoni'),
    ('Qatar', 'Qatar'),
    ("Qirg'iziston", "Qirg'iziston"),
    ('Tojikiston', 'Tojikiston'),
    ('Belarus', 'Belarus'),
    ('Ozarbayjon', 'Ozarbayjon'),
    ('Gruziya', 'Gruziya'),
    ('Germaniya', 'Germaniya'),
    ('Polsha', 'Polsha'),
    ('Chexiya', 'Chexiya'),
    ('Italiya', 'Italiya'),
    ('AQSH', 'AQSH'),
    ('Kanada', 'Kanada'),
    ('Buyuk Britaniya', 'Buyuk Britaniya'),
    ('Boshqa', 'Boshqa'),
]

PROVINCE_MAP = {
    'Rossiya': [
        'Moskva',
        'Moskva viloyati',
        'Sankt-Peterburg',
        'Leningrad viloyati',
        'Krasnodar',
        'Stavropol',
        'Yekaterinburg (Sverdlovsk)',
        'Novosibirsk',
        'Tatarstan',
    ],
    "Qozog'iston": [
        'Almati shahri',
        'Almati viloyati',
        'Astana',
        'Shymkent',
        'Karaganda',
        'Turkistan',
        'Aktobe',
    ],
    'Koreya Respublikasi': [
        'Seul',
        'Incheon',
        'Gyeonggi',
        'Busan',
        'Daegu',
        'Daejeon',
        'Ulsan',
        'Gwangju',
    ],
    'Turkiya': [
        'Istanbul',
        'Ankara',
        'Izmir',
        'Bursa',
        'Antalya',
        'Konya',
        'Mersin',
        'Gaziantep',
    ],
    'Birlashgan Arab Amirliklari': [
        'Dubai',
        'Abu-Dabi',
        'Sharja',
        'Ajman',
        'Ras al-Xayma',
        'Fujayra',
        'Umm al-Quvayn',
    ],
    'Saudiya Arabistoni': [
        'Riyod',
        'Jidda',
        'Makka',
        'Madina',
        'Dammam',
        'Sharqiya',
        'Tabuk',
    ],
    'Qatar': [
        'Doha',
        'Al Rayyan',
        'Al Wakrah',
    ],
    "Qirg'iziston": [
        'Bishkek',
        'Osh',
        'Jalolobod',
        'Chuy',
        'Issiqko\'l',
    ],
    'Tojikiston': [
        'Dushanbe',
        'Sug\'d',
        'Xatlon',
        'GBAO',
    ],
    'Belarus': [
        'Minsk',
        'Brest',
        'Vitebsk',
        'Gomel',
        'Grodno',
        'Mogilev',
    ],
    'Ozarbayjon': [
        'Boku',
        'Ganja',
        'Sumqayit',
        'Lankaran',
    ],
    'Gruziya': [
        'Tbilisi',
        'Batumi',
        'Kutaisi',
        'Rustavi',
    ],
    'Germaniya': [
        'Berlin',
        'Bavariya',
        'Nordrhein-Westfalen',
        'Baden-Wyurtemberg',
        'Gessen',
        'Gamburg',
        'Saksoniya',
    ],
    'Polsha': [
        'Varshava (Mazovya)',
        'Krakov (Malopolska)',
        'Sileziya',
        'Poznan (Buyuk Polsha)',
        'Gdansk (Pomeraniya)',
        'Vroclav (Quyi Sileziya)',
    ],
    'Chexiya': [
        'Praga',
        'Brno (Janubiy Moraviya)',
        'Ostrava (Moraviya-Sileziya)',
        'Plzen',
        'Usti nad Labem',
    ],
    'Italiya': [
        'Rim (Latsio)',
        'Milan (Lombardiya)',
        'Turin (Pyemont)',
        'Neapol (Kampaniya)',
        'Bolonya (Emiliya-Romanya)',
        'Florensiya (Toskana)',
    ],
    'AQSH': [
        'Nyu-York',
        'Kaliforniya',
        'Texas',
        'Florida',
        'Illinoys',
        'Nyu-Jersi',
        'Vashington',
    ],
    'Kanada': [
        'Ontario',
        'Kvebek',
        'Britaniya Kolumbiyasi',
        'Alberta',
        'Manitoba',
    ],
    'Buyuk Britaniya': [
        'London',
        'Angliya (boshqa)',
        'Shotlandiya',
        'Uels',
        'Shimoliy Irlandiya',
    ],
}


class MigrationYouthForm(forms.ModelForm):
    destination_country = forms.ChoiceField(
        choices=[('', 'Tanlang')] + COUNTRY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Davlat",
    )
    destination_province = forms.ChoiceField(
        choices=[('', 'Tanlang')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Provinsiya",
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        qs = Yosh.objects.all()
        if user and not getattr(user, 'is_site_admin', False) and user.mahalla:
            qs = qs.filter(mahalla=user.mahalla)

        if self.instance and self.instance.pk:
            qs = qs.filter(Q(migration_profile__isnull=True) | Q(pk=self.instance.yosh_id))
        else:
            qs = qs.filter(migration_profile__isnull=True)

        self.fields['yosh'].queryset = qs

        selected_country = self.data.get('destination_country') or getattr(self.instance, 'destination_country', '')
        selected_province = self.data.get('destination_province') or getattr(self.instance, 'destination_province', '')

        country_values = [val for val, _ in self.fields['destination_country'].choices]
        if selected_country and selected_country not in country_values:
            self.fields['destination_country'].choices.append((selected_country, selected_country))

        province_list = PROVINCE_MAP.get(selected_country, [])
        province_choices = [('', 'Tanlang')] + [(p, p) for p in province_list] + [('Boshqa', 'Boshqa')]
        if selected_province and selected_province not in [val for val, _ in province_choices]:
            province_choices.append((selected_province, selected_province))

        self.fields['destination_province'].choices = province_choices
        self.fields['destination_province'].widget.attrs['data-selected'] = selected_province or ''

    class Meta:
        model = MigrationYouth
        fields = [
            'yosh',
            'departure_date',
            'destination_country',
            'destination_province',
            'destination_address',
            'reason',
        ]
        widgets = {
            'yosh': forms.Select(attrs={'class': 'form-select select2'}),
            'departure_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'destination_country': forms.TextInput(attrs={'class': 'form-control'}),
            'destination_province': forms.TextInput(attrs={'class': 'form-control'}),
            'destination_address': forms.TextInput(attrs={'class': 'form-control'}),
            'reason': forms.Select(attrs={'class': 'form-select'}),
        }


class MigrationMeetingForm(forms.ModelForm):
    show_work = forms.BooleanField(required=False, initial=False, label="Ish ma'lumotlarini kiritish")
    show_education = forms.BooleanField(required=False, initial=False, label="Ta'lim ma'lumotlarini kiritish")

    class Meta:
        model = MigrationMeeting
        fields = [
            'meeting_date',
            'photo',
            'return_date',
            'work_title',
            'work_income',
            'work_conditions_rating',
            'education_institution',
            'education_direction',
            'education_course',
            'description',
        ]
        widgets = {
            'meeting_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'return_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'work_title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Masalan: Quruvchi'}),
            'work_income': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Dollar ($) yoki Mahalliy valyutada'}),
            'work_conditions_rating': forms.HiddenInput(),  # Will be handled by JS star widget
            'education_institution': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'OTM yoki Kollej nomi'}),
            'education_direction': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Fakultet yoki yo\'nalish'}),
            'education_course': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10', 'placeholder': '1'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Suhbat haqida qo\'shimcha ma\'lumot...'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        show_work = cleaned_data.get('show_work')
        show_education = cleaned_data.get('show_education')

        if not show_work and not show_education:
            raise ValidationError("Iltimos, kamida bitta bo'limni (Ish yoki Ta'lim) tanlang va ma'lumotlarni to'ldiring.")

        # Clear fields if not shown to ensure clean data
        if not show_work:
            cleaned_data['work_title'] = None
            cleaned_data['work_income'] = None
            cleaned_data['work_conditions_rating'] = None
        else:
            if not cleaned_data.get('work_title'):
                self.add_error('work_title', "Ish nomi kiritilishi shart.")

        if not show_education:
            cleaned_data['education_institution'] = None
            cleaned_data['education_direction'] = None
            cleaned_data['education_course'] = None
        else:
            if not cleaned_data.get('education_institution'):
                self.add_error('education_institution', "Ta'lim muassasasi nomi kiritilishi shart.")

        return cleaned_data
