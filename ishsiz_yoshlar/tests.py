from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.test import TestCase
from django.urls import reverse

from .forms import AssistanceForm
from .models import AssistanceInfo, UnemployedYouth
from core.models import Mahalla, User, Yosh


class AssistanceFormValidationTests(TestCase):
    def test_requires_document_when_provided_is_true(self):
        form = AssistanceForm(
            data={
                'provided': 'on',
                'assistance_type': 'ISH',
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('document', form.errors)

    def test_accepts_document_when_provided_is_true(self):
        document = SimpleUploadedFile(
            name='tasdiq.pdf',
            content=b'%PDF-1.4 assistance doc',
            content_type='application/pdf',
        )
        form = AssistanceForm(
            data={
                'provided': 'on',
                'assistance_type': 'ISH',
            },
            files={'document': document},
        )

        self.assertTrue(form.is_valid())


class AssistanceReplacementFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='admin_user',
            password='secret123',
            full_name='Admin User',
            role='SUPER_ADMIN',
        )
        self.mahalla = Mahalla.objects.create(name='Test Mahalla')
        self.yosh = Yosh.objects.create(
            fullname='Test Yosh',
            birth_date='2000-01-01',
            passport_number='AB1234567',
            jshshir='12345678901234',
            address='Test manzil',
            mahalla=self.mahalla,
        )
        self.unemployed = UnemployedYouth.objects.create(
            yosh=self.yosh,
            category='QOLGAN',
        )
        old_document = SimpleUploadedFile(
            name='old_tasdiq.pdf',
            content=b'%PDF-1.4 old',
            content_type='application/pdf',
        )
        self.assistance = AssistanceInfo.objects.create(
            unemployed_youth=self.unemployed,
            provided=True,
            assistance_type='ISH',
            date_provided='2026-02-01',
            document=old_document,
        )
        self.client.login(username='admin_user', password='secret123')
        self.url = reverse('ishsiz_yoshlar:assistance_update', kwargs={'pk': self.unemployed.pk})

    def test_second_assistance_requires_confirmation(self):
        new_document = SimpleUploadedFile(
            name='new_tasdiq.pdf',
            content=b'%PDF-1.4 new',
            content_type='application/pdf',
        )
        response = self.client.post(
            self.url,
            data={
                'provided': 'on',
                'assistance_type': 'KREDIT',
                'date_provided': '2026-02-08',
                'document': new_document,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Yangi yordamni saqlash uchun")
        self.assistance.refresh_from_db()
        self.assertEqual(self.assistance.assistance_type, 'ISH')
        self.assertEqual(str(self.assistance.date_provided), '2026-02-01')

    def test_confirmed_replacement_clears_old_and_saves_new(self):
        old_document_name = self.assistance.document.name
        new_document = SimpleUploadedFile(
            name='new_tasdiq.pdf',
            content=b'%PDF-1.4 replacement',
            content_type='application/pdf',
        )

        response = self.client.post(
            self.url,
            data={
                'provided': 'on',
                'assistance_type': 'KREDIT',
                'date_provided': '2026-02-08',
                'replace_confirmed': '1',
                'document': new_document,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assistance.refresh_from_db()
        self.assertEqual(self.assistance.assistance_type, 'KREDIT')
        self.assertEqual(str(self.assistance.date_provided), '2026-02-08')
        self.assertIn('new_tasdiq', self.assistance.document.name)
        self.assertNotEqual(self.assistance.document.name, old_document_name)


class SvodTabsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='leader_user',
            password='secret123',
            full_name='Leader User',
            role='YETAKCHI',
        )
        self.mahalla = Mahalla.objects.create(name='Tab Test Mahalla')
        yosh = Yosh.objects.create(
            fullname='Tab Test Yosh',
            birth_date='2001-01-01',
            passport_number='AC1234567',
            jshshir='22345678901234',
            address='Tab test manzil',
            mahalla=self.mahalla,
        )
        UnemployedYouth.objects.create(yosh=yosh, category='QOLGAN')
        self.client.login(username='leader_user', password='secret123')

    def test_svod_route_opens_tabs_template_with_mahalla_tab(self):
        response = self.client.get(reverse('ishsiz_yoshlar:svod'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ishsiz_yoshlar/svod_tabs.html')
        self.assertEqual(response.context['active_tab'], 'mahalla')

    def test_leader_svod_route_opens_same_template_with_leader_tab(self):
        response = self.client.get(reverse('ishsiz_yoshlar:leader_svod'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ishsiz_yoshlar/svod_tabs.html')
        self.assertEqual(response.context['active_tab'], 'leader')

    def test_professional_svod_route_opens_same_template_with_professional_tab(self):
        response = self.client.get(reverse('ishsiz_yoshlar:professional_svod'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ishsiz_yoshlar/svod_tabs.html')
        self.assertEqual(response.context['active_tab'], 'professional')


class YoshAutocompleteViewTests(TestCase):
    def setUp(self):
        self.mahalla_1 = Mahalla.objects.create(name='Autocomplete Mahalla 1')
        self.mahalla_2 = Mahalla.objects.create(name='Autocomplete Mahalla 2')

        self.user = User.objects.create_user(
            username='yetakchi_autocomplete',
            password='secret123',
            full_name='Yetakchi',
            role='YETAKCHI',
            mahalla=self.mahalla_1,
        )

        self.yosh_allowed = Yosh.objects.create(
            fullname='Ali Valiyev',
            birth_date='2002-01-01',
            passport_number='AD1234567',
            jshshir='33345678901234',
            address='A manzil',
            mahalla=self.mahalla_1,
        )
        self.yosh_other_mahalla = Yosh.objects.create(
            fullname='Sardor Karimov',
            birth_date='2003-01-01',
            passport_number='AE1234567',
            jshshir='43345678901234',
            address='B manzil',
            mahalla=self.mahalla_2,
        )
        self.yosh_already_registered = Yosh.objects.create(
            fullname='Aliyeva Nodira',
            birth_date='2004-01-01',
            passport_number='AF1234567',
            jshshir='53345678901234',
            address='C manzil',
            mahalla=self.mahalla_1,
        )
        UnemployedYouth.objects.create(yosh=self.yosh_already_registered, category='QOLGAN')

        self.url = reverse('ishsiz_yoshlar:yosh_autocomplete')
        self.client.login(username='yetakchi_autocomplete', password='secret123')

    def test_returns_only_user_mahalla_and_not_registered_youth(self):
        response = self.client.get(self.url, {'q': 'Ali'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        returned_texts = [item['text'] for item in data['results']]

        self.assertTrue(any('Ali Valiyev' in text for text in returned_texts))
        self.assertFalse(any('Aliyeva Nodira' in text for text in returned_texts))
        self.assertFalse(any('Sardor Karimov' in text for text in returned_texts))
