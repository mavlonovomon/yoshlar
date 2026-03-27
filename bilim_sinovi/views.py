import random
from collections import defaultdict
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import Lower, Trim
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView, View

from .forms import QuestionPackageImportForm, TestConfigForm
from .models import Question, QuestionPackage, TestConfig, TestResult


def _is_test_open(test_config):
    now = timezone.now()
    return bool(test_config.is_active and test_config.start_time <= now <= test_config.end_time)


def _get_test_questions(test_config):
    queryset = test_config.get_questions_queryset().select_related('subject', 'package')
    if not queryset.exists():
        return []

    max_count = test_config.questions_count

    if test_config.question_order == 'SEQUENTIAL':
        return list(queryset.order_by('id')[:max_count])

    questions = list(queryset)
    if len(questions) <= max_count:
        return questions
    return random.sample(questions, max_count)


def _latest_user_result(user, test_config):
    return (
        TestResult.objects
        .filter(user=user, test_config=test_config)
        .order_by('-finished_at', '-id')
        .first()
    )


def _attempts_count(user, test_config):
    return TestResult.objects.filter(user=user, test_config=test_config).count()


def _parse_questions_from_text(raw_text):
    parsed_questions = []
    lines = raw_text.splitlines()
    index = 0
    total_lines = len(lines)

    while index < total_lines:
        line = lines[index].strip()
        if not line:
            index += 1
            continue

        if not line.startswith('*'):
            raise ValueError(f"{index + 1}-qatorda savol '*' bilan boshlanishi shart.")

        question_text = line[1:].strip()
        if not question_text:
            raise ValueError(f"{index + 1}-qatorda savol matni bo'sh bo'lishi mumkin emas.")

        index += 1
        options = []
        while index < total_lines and len(options) < 4:
            option_line = lines[index].strip()
            if not option_line:
                index += 1
                continue

            prefix = option_line[0]
            if prefix not in {'+', '-'}:
                raise ValueError(f"{index + 1}-qatorda javob '+' yoki '-' bilan boshlanishi kerak.")

            option_text = option_line[1:].strip()
            if not option_text:
                raise ValueError(f"{index + 1}-qatorda javob varianti bo'sh bo'lishi mumkin emas.")

            options.append((prefix, option_text, index + 1))
            index += 1

        if len(options) != 4:
            raise ValueError(f"'{question_text[:40]}' savolida aniq 4 ta variant bo'lishi kerak.")

        correct_indexes = [idx for idx, (prefix, _, __) in enumerate(options) if prefix == '+']
        if len(correct_indexes) != 1:
            raise ValueError(f"'{question_text[:40]}' savolida aniq 1 ta '+' bo'lishi shart.")

        answer_letters = ['A', 'B', 'C', 'D']
        parsed_questions.append({
            'text': question_text,
            'option_a': options[0][1],
            'option_b': options[1][1],
            'option_c': options[2][1],
            'option_d': options[3][1],
            'correct_answer': answer_letters[correct_indexes[0]],
        })

    if not parsed_questions:
        raise ValueError("Faylda import qilish uchun savollar topilmadi.")

    return parsed_questions


class TestOrganizerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return bool(self.request.user.is_authenticated and getattr(self.request.user, 'is_site_admin', False))

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Bu bo'lim faqat Rahbar/Admin uchun.")
            return redirect('bilim_sinovi:test_list')
        return super().handle_no_permission()


class TestParticipantRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return bool(user.is_authenticated and getattr(user, 'is_leader', False))

    def handle_no_permission(self):
        user = self.request.user
        if user.is_authenticated and getattr(user, 'is_site_admin', False):
            messages.info(self.request, "Siz uchun test yechish emas, test tashkillashtirish bo'limi ochildi.")
            return redirect('bilim_sinovi:test_manage_list')
        if user.is_authenticated:
            messages.error(self.request, "Test yechish faqat yetakchilar uchun.")
            return redirect('dashboard')
        return super().handle_no_permission()


class TestListView(LoginRequiredMixin, ListView):
    model = TestConfig
    template_name = 'bilim_sinovi/test_list.html'
    context_object_name = 'tests'

    def get(self, request, *args, **kwargs):
        if getattr(request.user, 'is_site_admin', False):
            return redirect('bilim_sinovi:test_manage_list')
        if not getattr(request.user, 'is_leader', False):
            messages.error(request, "Test yechish faqat yetakchilar uchun.")
            return redirect('dashboard')
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        now = timezone.now()
        return (
            TestConfig.objects
            .select_related('subject')
            .prefetch_related('question_packages__category')
            .filter(
                is_active=True,
                start_time__lte=now,
                end_time__gte=now,
            )
            .order_by('end_time')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_results = {}
        attempts_map = {}
        if self.request.user.is_authenticated:
            for result in (
                TestResult.objects
                .filter(user=self.request.user)
                .order_by('test_config_id', '-finished_at', '-id')
            ):
                user_results.setdefault(result.test_config_id, result)
            for row in (
                TestResult.objects
                .filter(user=self.request.user)
                .values('test_config_id')
                .annotate(total=Count('id'))
            ):
                attempts_map[row['test_config_id']] = row['total']
        context['user_results'] = user_results
        context['attempts_map'] = attempts_map
        return context


class TestManageListView(LoginRequiredMixin, TestOrganizerRequiredMixin, ListView):
    model = TestConfig
    template_name = 'bilim_sinovi/manage_list.html'
    context_object_name = 'tests'

    def get_queryset(self):
        return (
            TestConfig.objects
            .select_related('subject')
            .prefetch_related('question_sets', 'question_packages')
            .order_by('-created_at')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()
        return context


class QuestionPackageListView(LoginRequiredMixin, TestOrganizerRequiredMixin, ListView):
    model = QuestionPackage
    template_name = 'bilim_sinovi/question_package_list.html'
    context_object_name = 'packages'

    def get_queryset(self):
        return (
            QuestionPackage.objects
            .select_related('category', 'created_by')
            .annotate(question_count=Count('questions'))
            .order_by('-created_at')
        )


class QuestionPackageImportView(LoginRequiredMixin, TestOrganizerRequiredMixin, FormView):
    template_name = 'bilim_sinovi/question_package_import.html'
    form_class = QuestionPackageImportForm
    success_url = reverse_lazy('bilim_sinovi:question_package_list')

    def form_valid(self, form):
        txt_file = form.cleaned_data['txt_file']
        category = form.cleaned_data['category']
        package_name = form.cleaned_data['package_name'].strip()

        try:
            raw_text = txt_file.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            form.add_error('txt_file', "Fayl UTF-8 kodirovkada bo'lishi kerak.")
            return self.form_invalid(form)

        try:
            parsed_questions = _parse_questions_from_text(raw_text)
        except ValueError as exc:
            form.add_error('txt_file', str(exc))
            return self.form_invalid(form)

        normalized_existing = set(
            Question.objects
            .filter(subject=category)
            .annotate(normalized_text=Lower(Trim('text')))
            .values_list('normalized_text', flat=True)
        )

        with transaction.atomic():
            package = QuestionPackage.objects.create(
                name=package_name,
                category=category,
                created_by=self.request.user,
                source_file=txt_file.name or '',
                parsed_count=len(parsed_questions),
            )

            imported_count = 0
            skipped_count = 0

            for parsed_question in parsed_questions:
                normalized_text = parsed_question['text'].strip().lower()
                if normalized_text in normalized_existing:
                    skipped_count += 1
                    continue

                Question.objects.create(
                    subject=category,
                    package=package,
                    file_source=txt_file.name or '',
                    **parsed_question,
                )
                normalized_existing.add(normalized_text)
                imported_count += 1

            package.imported_count = imported_count
            package.skipped_count = skipped_count
            package.save(update_fields=['imported_count', 'skipped_count'])

        messages.success(
            self.request,
            (
                f"Paket saqlandi: o'qildi {package.parsed_count} ta, "
                f"saqlandi {package.imported_count} ta, "
                f"o'tkazib yuborildi {package.skipped_count} ta."
            ),
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Savollar paketini import qilish"
        return context


class TestResultsDashboardView(LoginRequiredMixin, TestOrganizerRequiredMixin, TemplateView):
    template_name = 'bilim_sinovi/results_dashboard.html'

    @staticmethod
    def _parse_date(value):
        if not value:
            return None
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        q = (self.request.GET.get('q') or '').strip()
        test_id = (self.request.GET.get('test') or '').strip()
        from_raw = (self.request.GET.get('from') or '').strip()
        to_raw = (self.request.GET.get('to') or '').strip()

        from_date = self._parse_date(from_raw)
        to_date = self._parse_date(to_raw)
        if from_raw and not from_date:
            messages.warning(self.request, "Boshlanish sana formati noto'g'ri. YYYY-MM-DD kiriting.")
        if to_raw and not to_date:
            messages.warning(self.request, "Tugash sana formati noto'g'ri. YYYY-MM-DD kiriting.")

        results_qs = (
            TestResult.objects
            .select_related('user__mahalla', 'test_config')
            .order_by('-finished_at', '-id')
        )
        if q:
            results_qs = results_qs.filter(
                Q(user__full_name__icontains=q) |
                Q(user__username__icontains=q) |
                Q(test_config__title__icontains=q)
            )
        if test_id.isdigit():
            results_qs = results_qs.filter(test_config_id=int(test_id))
        if from_date:
            results_qs = results_qs.filter(finished_at__date__gte=from_date)
        if to_date:
            results_qs = results_qs.filter(finished_at__date__lte=to_date)

        all_attempts = list(results_qs)

        attempt_no_map = {}
        per_pair_count = defaultdict(int)
        for attempt in reversed(all_attempts):
            pair_key = (attempt.user_id, attempt.test_config_id)
            per_pair_count[pair_key] += 1
            attempt_no_map[attempt.id] = per_pair_count[pair_key]

        leader_stats = {}
        test_stats = {}

        for attempt in all_attempts:
            percentage = (
                (attempt.correct_answers_count / attempt.total_questions) * 100
                if attempt.total_questions else 0
            )
            attempt.percentage = round(percentage, 1)
            attempt.attempt_no = attempt_no_map.get(attempt.id, 1)

            leader_key = attempt.user_id
            leader_item = leader_stats.get(leader_key)
            if not leader_item:
                leader_item = {
                    'user': attempt.user,
                    'mahalla_name': attempt.user.mahalla.name if attempt.user.mahalla else '-',
                    'sector': attempt.user.get_sector_display() if attempt.user.sector else '-',
                    'attempts_count': 0,
                    'tests_set': set(),
                    'total_correct': 0,
                    'total_questions': 0,
                    'best_percentage': 0.0,
                    'last_finished_at': attempt.finished_at,
                }
                leader_stats[leader_key] = leader_item

            leader_item['attempts_count'] += 1
            leader_item['tests_set'].add(attempt.test_config_id)
            leader_item['total_correct'] += attempt.correct_answers_count
            leader_item['total_questions'] += attempt.total_questions
            leader_item['best_percentage'] = max(leader_item['best_percentage'], percentage)
            if attempt.finished_at and (
                not leader_item['last_finished_at'] or attempt.finished_at > leader_item['last_finished_at']
            ):
                leader_item['last_finished_at'] = attempt.finished_at

            test_key = attempt.test_config_id
            test_item = test_stats.get(test_key)
            if not test_item:
                test_item = {
                    'test': attempt.test_config,
                    'participants_set': set(),
                    'attempts_count': 0,
                    'total_correct': 0,
                    'total_questions': 0,
                    'best_percentage': percentage,
                    'min_percentage': percentage,
                    'last_finished_at': attempt.finished_at,
                }
                test_stats[test_key] = test_item

            test_item['participants_set'].add(attempt.user_id)
            test_item['attempts_count'] += 1
            test_item['total_correct'] += attempt.correct_answers_count
            test_item['total_questions'] += attempt.total_questions
            test_item['best_percentage'] = max(test_item['best_percentage'], percentage)
            test_item['min_percentage'] = min(test_item['min_percentage'], percentage)
            if attempt.finished_at and (
                not test_item['last_finished_at'] or attempt.finished_at > test_item['last_finished_at']
            ):
                test_item['last_finished_at'] = attempt.finished_at

        attempts_rows = all_attempts[:300]

        leader_rows = []
        for item in leader_stats.values():
            avg_percentage = (
                (item['total_correct'] / item['total_questions']) * 100
                if item['total_questions'] else 0
            )
            leader_rows.append({
                'user': item['user'],
                'mahalla_name': item['mahalla_name'],
                'sector': item['sector'],
                'attempts_count': item['attempts_count'],
                'tests_count': len(item['tests_set']),
                'avg_percentage': round(avg_percentage, 1),
                'best_percentage': round(item['best_percentage'], 1),
                'last_finished_at': item['last_finished_at'],
            })
        leader_rows.sort(key=lambda row: (row['avg_percentage'], row['best_percentage'], row['attempts_count']), reverse=True)
        for index, row in enumerate(leader_rows, start=1):
            row['rank'] = index

        test_rows = []
        for item in test_stats.values():
            avg_percentage = (
                (item['total_correct'] / item['total_questions']) * 100
                if item['total_questions'] else 0
            )
            test_rows.append({
                'test': item['test'],
                'participants_count': len(item['participants_set']),
                'attempts_count': item['attempts_count'],
                'avg_percentage': round(avg_percentage, 1),
                'best_percentage': round(item['best_percentage'], 1),
                'min_percentage': round(item['min_percentage'], 1),
                'last_finished_at': item['last_finished_at'],
            })
        test_rows.sort(key=lambda row: (row['avg_percentage'], row['participants_count'], row['attempts_count']), reverse=True)

        tests = TestConfig.objects.order_by('-created_at')
        context.update({
            'tests': tests,
            'q': q,
            'selected_test': int(test_id) if test_id.isdigit() else None,
            'from_date': from_raw,
            'to_date': to_raw,
            'attempts_rows': attempts_rows,
            'leader_rows': leader_rows,
            'test_rows': test_rows,
            'total_attempts': len(all_attempts),
            'shown_attempts': len(attempts_rows),
        })
        return context


class TestConfigCreateView(LoginRequiredMixin, TestOrganizerRequiredMixin, CreateView):
    model = TestConfig
    form_class = TestConfigForm
    template_name = 'bilim_sinovi/manage_form.html'
    success_url = reverse_lazy('bilim_sinovi:test_manage_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        if not self.object.question_sets.exists() and self.object.subject_id:
            self.object.question_sets.set([self.object.subject_id])
        messages.success(self.request, "Test muvaffaqiyatli yaratildi.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Yangi Test Tashkil Qilish"
        context['submit_label'] = "Yaratish"
        return context


class TestConfigUpdateView(LoginRequiredMixin, TestOrganizerRequiredMixin, UpdateView):
    model = TestConfig
    form_class = TestConfigForm
    template_name = 'bilim_sinovi/manage_form.html'
    success_url = reverse_lazy('bilim_sinovi:test_manage_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        if not self.object.question_sets.exists() and self.object.subject_id:
            self.object.question_sets.set([self.object.subject_id])
        messages.success(self.request, "Test sozlamalari yangilandi.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Test Sozlamasini Tahrirlash"
        context['submit_label'] = "Saqlash"
        return context


class TestStartView(LoginRequiredMixin, TestParticipantRequiredMixin, View):
    def post(self, request, pk):
        test_config = get_object_or_404(TestConfig, pk=pk)

        attempts = _attempts_count(request.user, test_config)
        if attempts >= test_config.max_attempts:
            messages.warning(request, "Siz bu test uchun maksimal urinishlar sonidan foydalangansiz.")
            return redirect('bilim_sinovi:test_result', pk=pk)

        if not _is_test_open(test_config):
            messages.warning(request, "Test hozir yopiq yoki vaqt oralig'i tugagan.")
            return redirect('bilim_sinovi:test_list')

        return redirect('bilim_sinovi:test_detail', pk=pk)


class TestDetailView(LoginRequiredMixin, TestParticipantRequiredMixin, DetailView):
    model = TestConfig
    template_name = 'bilim_sinovi/test_detail.html'
    context_object_name = 'test'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        attempts = _attempts_count(request.user, self.object)
        if attempts >= self.object.max_attempts:
            messages.warning(request, "Ushbu test uchun urinish limiti tugagan.")
            return redirect('bilim_sinovi:test_result', pk=self.object.pk)

        if not _is_test_open(self.object):
            messages.warning(request, "Test hozir ochiq emas.")
            return redirect('bilim_sinovi:test_list')

        questions = _get_test_questions(self.object)
        if not questions:
            messages.error(request, "Test uchun savollar topilmadi. Rahbar/Admin bilan bog'laning.")
            return redirect('bilim_sinovi:test_list')

        request.session[f'bilim_test_{self.object.pk}_question_ids'] = [q.id for q in questions]

        context = self.get_context_data(object=self.object)
        context['questions'] = questions
        context['attempts_used'] = attempts
        context['attempts_left'] = max(self.object.max_attempts - attempts, 0)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        test_config = self.get_object()

        attempts = _attempts_count(request.user, test_config)
        if attempts >= test_config.max_attempts:
            messages.warning(request, "Ushbu test uchun urinish limiti tugagan.")
            return redirect('bilim_sinovi:test_result', pk=test_config.pk)

        if not _is_test_open(test_config):
            messages.warning(request, "Test vaqti tugagan.")
            return redirect('bilim_sinovi:test_list')

        session_key = f'bilim_test_{test_config.pk}_question_ids'
        question_ids = request.session.get(session_key) or []
        if not question_ids:
            question_ids = [q.id for q in _get_test_questions(test_config)]

        question_map = {q.id: q for q in Question.objects.filter(id__in=question_ids)}

        score = 0
        correct_count = 0
        answers_data = {}
        total_questions = len(question_ids)

        for q_id in question_ids:
            question = question_map.get(q_id)
            if not question:
                continue
            selected = request.POST.get(f'question_{q_id}')
            is_correct = bool(selected and selected == question.correct_answer)
            if is_correct:
                score += 1
                correct_count += 1

            answers_data[q_id] = {
                'selected': selected,
                'correct': question.correct_answer,
                'is_correct': is_correct,
            }

        TestResult.objects.create(
            user=request.user,
            test_config=test_config,
            score=score,
            correct_answers_count=correct_count,
            total_questions=total_questions,
            finished_at=timezone.now(),
            data=answers_data,
        )

        if session_key in request.session:
            del request.session[session_key]

        return redirect('bilim_sinovi:test_result', pk=test_config.pk)


class TestResultView(LoginRequiredMixin, TestParticipantRequiredMixin, DetailView):
    model = TestConfig
    template_name = 'bilim_sinovi/result.html'
    context_object_name = 'test'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not _latest_user_result(request.user, self.object):
            messages.warning(request, "Bu test bo'yicha natija topilmadi.")
            return redirect('bilim_sinovi:test_list')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result = _latest_user_result(self.request.user, self.object)

        attempts_used = _attempts_count(self.request.user, self.object)
        percentage = (result.correct_answers_count / result.total_questions * 100) if result.total_questions > 0 else 0

        context['result'] = result
        context['percentage'] = percentage
        context['attempts_used'] = attempts_used
        context['max_attempts'] = self.object.max_attempts
        return context
