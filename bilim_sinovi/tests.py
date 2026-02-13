from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import User

from .models import Question, Subject, TestConfig, TestResult


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
