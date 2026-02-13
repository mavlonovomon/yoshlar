from django.db import models
from django.core.validators import FileExtensionValidator
from core.models import Yosh, Mahalla

class OtaliqLeader(models.Model):
    LEVEL_CHOICES = [
        ('TUMAN', 'Tuman darajasi'),
        ('VILOYAT', 'Viloyat darajasi'),
        ('RESPUBLIKA', 'Respublika darajasi'),
        ('OTM', 'OTM'),
    ]
    ORG_TYPES = [
        ('ORGAN', 'Huquq-tartibot organlari'),
        ('HOKIMLIK', 'Hokimlik'),
        ('BOSHQA', 'Boshqa tashkilot'),
    ]

    full_name = models.CharField(max_length=255, verbose_name="F.I.Sh")
    position = models.CharField(max_length=255, verbose_name="Lavozimi")
    organization_type = models.CharField(max_length=20, choices=ORG_TYPES, default='ORGAN', verbose_name="Tashkilot turi")
    organization_name = models.CharField(max_length=255, verbose_name="Tashkilot nomi")
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, verbose_name="Darajasi")
    phone_number = models.CharField(max_length=20, verbose_name="Telefon raqami")
    sector = models.CharField(max_length=100, blank=True, null=True, verbose_name="Soha")

    class Meta:
        ordering = ['full_name']
        verbose_name = "Otaliq mas’uli"
        verbose_name_plural = "Otaliq mas’ullari"

    def __str__(self):
        return f"{self.full_name} ({self.organization_name})"

class OtaliqYouth(models.Model):
    CATEGORY_CHOICES = [
        ('GIYOHVAND', 'Giyohvandlar, psixotrop va ularning analoglari hamda spirtli ichimliklarga ruju qo\'yganlar'),
        ('SUDLANGAN', 'Ilgari sudlangan (probatsiya va profilaktik hisobda turmaydiganlar)'),
        ('JINOYATCHI', 'Jinoyat sodir etgan voyaga yetmaganlar'),
        ('MJTK_56', 'Ma\'muriy huquqbuzarlik (MjTK 56-m)'),
        ('MEHRIBONLIK', 'Mehribonlik uyidan chiqqanlar'),
        ('PROBATSIYA', 'Probatsiya hisobida'),
        ('AGRESSIV', 'Agressiv xulq-atvorli yoshlar'),
        ('YOT_GOYA', 'Yot g\'oyalar ta\'siriga tushib qolganlar'),
    ]

    yosh = models.OneToOneField(Yosh, on_delete=models.CASCADE, related_name='otaliq_profile', verbose_name="Yosh")
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, verbose_name="Toifa")
    leader = models.ForeignKey(OtaliqLeader, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_youths', verbose_name="Biriktirilgan rahbar")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Qo'shilgan vaqti")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Tahrirlangan vaqti")
    is_deleted = models.BooleanField(default=False, verbose_name="O'chirilgan")

    class Meta:
        verbose_name = "Otaliqqa olingan yosh"
        verbose_name_plural = "Otaliqqa olingan yoshlar"

    def __str__(self):
        return self.yosh.fullname

class OtaliqMeeting(models.Model):
    otaliq_youth = models.ForeignKey(OtaliqYouth, on_delete=models.CASCADE, related_name='meetings', verbose_name="Otaliq yoshi")
    meeting_date = models.DateTimeField(verbose_name="Uchrashuv vaqti")
    photo = models.ImageField(upload_to='otaliq/meetings/', verbose_name="Uchrashuv rasmi", validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])])
    description = models.TextField(verbose_name="Uchrashuv mazmuni/izoh")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Otaliq uchrashuvi"
        verbose_name_plural = "Otaliq uchrashuvlari"
        ordering = ['-meeting_date']

class OtaliqAssistance(models.Model):
    ASSISTANCE_TYPES = [
        ('MODDIY', 'Moddiy yordam'),
        ('PSIXOLOGIK', 'Psixologik ko\'mak'),
        ('ISH', 'Ishga joylashtirish'),
        ('OQUV', 'O\'qishga yo\'naltirish'),
        ('TIBBIY', 'Tibbiy yordam'),
        ('BOSHQA', 'Boshqa yordam'),
    ]

    otaliq_youth = models.OneToOneField(OtaliqYouth, on_delete=models.CASCADE, related_name='assistance', verbose_name="Otaliq yoshi")
    provided = models.BooleanField(default=False, verbose_name="Yordam ko'rsatilgan")
    assistance_type = models.CharField(max_length=50, choices=ASSISTANCE_TYPES, blank=True, null=True, verbose_name="Yordam yo'nalishi")
    date_provided = models.DateField(blank=True, null=True, verbose_name="Yordam ko'rsatilgan sana")
    description = models.TextField(blank=True, null=True, verbose_name="Yordam tavsifi")
    document = models.FileField(upload_to='otaliq/assistance_docs/', blank=True, null=True, verbose_name="Tasdiqlovchi hujjat", validators=[FileExtensionValidator(['pdf', 'zip', 'rar', 'jpg', 'png'])])
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Yordam ma'lumoti"
        verbose_name_plural = "Yordam ma'lumotlari"
