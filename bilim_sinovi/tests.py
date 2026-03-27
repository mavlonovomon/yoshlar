from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import User

from .forms import TestConfigForm
from .models import Question, QuestionPackage, Subject, TestConfig, TestResult


class BilimSinoviFlowTests(TestCase):
    def setUp(self):
        self.leader = User.objects.create_user(
            username='yetakchi_test',
            password='secret123',
            full_name='Yetakchi Test',
            role='YETAKCHI',
        )
        self.rahbar = User.objects.create_user(
            username='rahbar_test',
            password='secret123',
            full_name='Rahbar Test',
            role='RAHBAR',
        )
        self.subject = Subject.objects.create(name='Matematika', description='Demo fan')
        self.questions = []
        for idx in range(1, 6):
            self.questions.append(
                Question.objects.create(
                    subject=self.subject,
                    text=f'Savol {idx}',
                    option_a='A',
                    option_b='B',
                    option_c='C',
                    option_d='D',
                    correct_answer='A',
                )
            )

        now = timezone.now()
        self.test_config = TestConfig.objects.create(
            title='Test 1',
            subject=self.subject,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            duration_minutes=20,
            questions_count=3,
            question_order='SEQUENTIAL',
            max_attempts=1,
            is_active=True,
        )

    def test_rahbar_redirected_to_manage_page(self):
        self.client.login(username='rahbar_test', password='secret123')
        response = self.client.get(reverse('bilim_sinovi:test_list'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('bilim_sinovi:test_manage_list'))

        manage_response = self.client.get(reverse('bilim_sinovi:test_manage_list'))
        self.assertEqual(manage_response.status_code, 200)

    def test_leader_cannot_access_manage_page(self):
        self.client.login(username='yetakchi_test', password='secret123')
        response = self.client.get(reverse('bilim_sinovi:test_manage_list'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('bilim_sinovi:test_list'))

    def test_sequential_question_order_used_in_test_detail(self):
        self.client.login(username='yetakchi_test', password='secret123')
        response = self.client.get(reverse('bilim_sinovi:test_detail', args=[self.test_config.pk]))
        self.assertEqual(response.status_code, 200)

        rendered_questions = response.context['questions']
        rendered_ids = [q.id for q in rendered_questions]
        expected_ids = [q.id for q in sorted(self.questions, key=lambda item: item.id)[:3]]
        self.assertEqual(rendered_ids, expected_ids)

    def test_max_attempts_is_enforced(self):
        self.client.login(username='yetakchi_test', password='secret123')

        detail_response = self.client.get(reverse('bilim_sinovi:test_detail', args=[self.test_config.pk]))
        self.assertEqual(detail_response.status_code, 200)
        questions = detail_response.context['questions']

        payload = {f'question_{q.pk}': q.correct_answer for q in questions}
        submit_response = self.client.post(reverse('bilim_sinovi:test_detail', args=[self.test_config.pk]), data=payload)
        self.assertEqual(submit_response.status_code, 302)
        self.assertEqual(TestResult.objects.filter(user=self.leader, test_config=self.test_config).count(), 1)

        second_start = self.client.post(reverse('bilim_sinovi:test_start', args=[self.test_config.pk]))
        self.assertEqual(second_start.status_code, 302)
        self.assertEqual(second_start.url, reverse('bilim_sinovi:test_result', args=[self.test_config.pk]))
        self.assertEqual(TestResult.objects.filter(user=self.leader, test_config=self.test_config).count(), 1)

    def test_rahbar_can_open_results_dashboard(self):
        self.client.login(username='rahbar_test', password='secret123')
        response = self.client.get(reverse('bilim_sinovi:test_results_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bilim_sinovi/results_dashboard.html')

    def test_leader_cannot_open_results_dashboard(self):
        self.client.login(username='yetakchi_test', password='secret123')
        response = self.client.get(reverse('bilim_sinovi:test_results_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('bilim_sinovi:test_list'))


class QuestionPackageImportTests(TestCase):
    def setUp(self):
        self.leader = User.objects.create_user(
            username='leader_pkg',
            password='secret123',
            full_name='Leader Pkg',
            role='YETAKCHI',
        )
        self.rahbar = User.objects.create_user(
            username='rahbar_pkg',
            password='secret123',
            full_name='Rahbar Pkg',
            role='RAHBAR',
        )
        self.subject = Subject.objects.create(name='Tarix')

    def test_only_admin_can_access_import_page(self):
        self.client.login(username='leader_pkg', password='secret123')
        leader_response = self.client.get(reverse('bilim_sinovi:question_package_import'))
        self.assertEqual(leader_response.status_code, 302)
        self.assertEqual(leader_response.url, reverse('bilim_sinovi:test_list'))

        self.client.login(username='rahbar_pkg', password='secret123')
        rahbar_response = self.client.get(reverse('bilim_sinovi:question_package_import'))
        self.assertEqual(rahbar_response.status_code, 200)

    def test_import_success_with_duplicate_skip(self):
        Question.objects.create(
            subject=self.subject,
            text='OZBEKISTON poytaxti qaysi shahar?',
            option_a='Samarqand',
            option_b='Buxoro',
            option_c='Xiva',
            option_d='Toshkent',
            correct_answer='D',
        )

        txt_content = (
            "* ozbekiston poytaxti qaysi shahar?\n"
            "- Samarqand\n"
            "- Buxoro\n"
            "- Nukus\n"
            "+ Toshkent\n"
            "\n"
            "* Amir Temur qachon tug'ilgan?\n"
            "- 1330\n"
            "- 1340\n"
            "+ 1336\n"
            "- 1338\n"
        )

        self.client.login(username='rahbar_pkg', password='secret123')
        response = self.client.post(
            reverse('bilim_sinovi:question_package_import'),
            data={
                'package_name': 'Tarix-1',
                'category': self.subject.pk,
                'txt_file': SimpleUploadedFile('history.txt', txt_content.encode('utf-8'), content_type='text/plain'),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('bilim_sinovi:question_package_list'))

        package = QuestionPackage.objects.get(name='Tarix-1')
        self.assertEqual(package.parsed_count, 2)
        self.assertEqual(package.imported_count, 1)
        self.assertEqual(package.skipped_count, 1)
        self.assertEqual(Question.objects.filter(package=package).count(), 1)

    def test_invalid_format_rolls_back_entire_import(self):
        invalid_txt_content = (
            "* Noto'g'ri savol\n"
            "- Variant 1\n"
            "+ Variant 2\n"
        )

        self.client.login(username='rahbar_pkg', password='secret123')
        response = self.client.post(
            reverse('bilim_sinovi:question_package_import'),
            data={
                'package_name': 'Xato paket',
                'category': self.subject.pk,
                'txt_file': SimpleUploadedFile('bad.txt', invalid_txt_content.encode('utf-8'), content_type='text/plain'),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "aniq 4 ta variant")
        self.assertFalse(QuestionPackage.objects.filter(name='Xato paket').exists())


class QuestionPackageFlowTests(TestCase):
    def setUp(self):
        self.leader = User.objects.create_user(
            username='yetakchi_pkg_flow',
            password='secret123',
            full_name='Yetakchi Pkg Flow',
            role='YETAKCHI',
        )
        self.rahbar = User.objects.create_user(
            username='rahbar_pkg_flow',
            password='secret123',
            full_name='Rahbar Pkg Flow',
            role='RAHBAR',
        )

        self.subject = Subject.objects.create(name='Matematika')
        self.package = QuestionPackage.objects.create(
            name='Matematika paket',
            category=self.subject,
            created_by=self.rahbar,
            parsed_count=2,
            imported_count=2,
            skipped_count=0,
        )

        self.package_questions = []
        for idx in range(1, 3):
            self.package_questions.append(
                Question.objects.create(
                    subject=self.subject,
                    package=self.package,
                    text=f'Paket savoli {idx}',
                    option_a='A',
                    option_b='B',
                    option_c='C',
                    option_d='D',
                    correct_answer='A',
                )
            )

        self.outside_question = Question.objects.create(
            subject=self.subject,
            text='Paketdan tashqari savol',
            option_a='A',
            option_b='B',
            option_c='C',
            option_d='D',
            correct_answer='A',
        )

    def test_test_config_validation_uses_package_question_count(self):
        now = timezone.now()
        form = TestConfigForm(data={
            'title': 'Paketli test',
            'subject': '',
            'question_sets': '',
            'question_packages': [self.package.pk],
            'start_time': now.strftime('%Y-%m-%dT%H:%M'),
            'end_time': (now + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),
            'duration_minutes': 10,
            'questions_count': 3,
            'question_order': 'SEQUENTIAL',
            'max_attempts': 1,
            'is_active': True,
        })

        self.assertFalse(form.is_valid())
        self.assertIn('questions_count', form.errors)

    def test_test_detail_uses_only_selected_package_questions(self):
        now = timezone.now()
        test_config = TestConfig.objects.create(
            title='Paket bo\'yicha test',
            subject=self.subject,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            duration_minutes=20,
            questions_count=2,
            question_order='SEQUENTIAL',
            max_attempts=1,
            is_active=True,
        )
        test_config.question_packages.set([self.package])

        self.client.login(username='yetakchi_pkg_flow', password='secret123')
        response = self.client.get(reverse('bilim_sinovi:test_detail', args=[test_config.pk]))
        self.assertEqual(response.status_code, 200)

        rendered_ids = {q.id for q in response.context['questions']}
        package_ids = {q.id for q in self.package_questions}
        self.assertEqual(rendered_ids, package_ids)
        self.assertNotIn(self.outside_question.id, rendered_ids)
