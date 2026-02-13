from django.shortcuts import render, redirect, get_object_or_404
import re
from collections import defaultdict
from datetime import timedelta

from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Case, When, BooleanField, Sum
from django.utils import timezone
from django.core.paginator import Paginator
from .models import (
    Mahalla,
    Yosh,
    Uchrashuv,
    User,
    MutolaaStatSnapshot,
    UstozAiStatSnapshot,
    UzchessStatSnapshot,
    QizlarAkademiyasiStatSnapshot,
)
from .forms import MahallaLoginForm, YoshForm, UchrashuvForm, UserProfileForm
from django.views.decorators.http import require_POST
from django.contrib import messages

from .mutolaa import fetch_and_store_mutolaa_snapshot, build_table
from .ustoz_ai import build_table as build_ustoz_table, fetch_and_store_ustoz_ai_snapshot
from .uzchess import build_table as build_uzchess_table, fetch_and_store_uzchess_snapshot
from .qizlar_akademiyasi import build_table as build_qizlar_table, fetch_and_store_qizlar_snapshot
from ishsiz_yoshlar.models import UnemployedYouth, Task
from migratsiya.models import MigrationYouth, MigrationMeeting
from otaliq.models import OtaliqYouth, OtaliqMeeting
from reyd.models import RaidEvent
from beshtashabbus.models import FiveInitiativeEvent
from yoqlama.models import AttendanceRecord
from intizom_jazo.models import DisciplineAction

# Since I missed UchrashuvForm in forms.py, I'll define a simple one here or via factory


def _is_management_user(user):
    return bool(
        user
        and (user.is_superuser or user.is_staff or getattr(user, 'role', None) in {'SUPER_ADMIN', 'RAHBAR'})
    )

def login_view(request):
    if request.method == 'POST':
        form = MahallaLoginForm(request.POST)
        if form.is_valid():
            mahalla = form.cleaned_data.get('mahalla')
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            
            user = None
            if mahalla:
                # Find leader of this mahalla
                user = User.objects.filter(mahalla=mahalla, role='YETAKCHI').first()
                if user and user.check_password(password):
                    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    return redirect('dashboard')
                else:
                    form.add_error(None, "Ushbu mahalla yetakchisi topilmadi yoki parol noto'g'ri")
            elif username:
                user = authenticate(request, username=username, password=password)
                if user:
                    login(request, user)
                    return redirect('dashboard')
                else:
                    form.add_error(None, "Login yoki parol noto'g'ri")
            else:
                form.add_error(None, "Mahalla tanlang yoki Admin login kiriting")
    else:
        form = MahallaLoginForm()
    
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def dashboard(request):
    user = request.user
    context = {}
    
    if _is_management_user(user):
        qs = Yosh.objects.all()
        meetings = Uchrashuv.objects.select_related('yosh', 'yetakchi', 'yosh__mahalla').all().order_by('-meeting_date')[:10]
        total_meetings_count = Uchrashuv.objects.count()
    else:
        qs = Yosh.objects.filter(mahalla=user.mahalla)
        meetings = Uchrashuv.objects.select_related('yosh', 'yetakchi', 'yosh__mahalla').filter(yosh__mahalla=user.mahalla).order_by('-meeting_date')[:10]
        total_meetings_count = Uchrashuv.objects.filter(yosh__mahalla=user.mahalla).count()

    context['total_yosh'] = qs.count()
    context['suhbat_bor'] = qs.annotate(has_meeting=Count('uchrashuvlar')).filter(has_meeting__gt=0).count()
    context['suhbat_yoq'] = context['total_yosh'] - context['suhbat_bor']
    context['total_meetings'] = total_meetings_count

    latest_meetings = list(meetings)
    for meeting in latest_meetings:
        if meeting.meeting_date:
            local_dt = timezone.localtime(meeting.meeting_date)
            meeting.meeting_date_str = local_dt.strftime('%d.%m.%Y')
            meeting.meeting_time_str = local_dt.strftime('%H:%M')
        else:
            meeting.meeting_date_str = ''
            meeting.meeting_time_str = ''
    context['latest_meetings'] = latest_meetings
    
    return render(request, 'dashboard.html', context)


def _safe_ratio(numerator, denominator):
    if not denominator:
        return None
    ratio = numerator / denominator
    if ratio < 0:
        return 0.0
    if ratio > 1:
        return 1.0
    return ratio


def _weighted_mean(weighted_values):
    valid = [(value, weight) for value, weight in weighted_values if value is not None]
    if not valid:
        return None
    weight_sum = sum(weight for _, weight in valid)
    if not weight_sum:
        return None
    return sum(value * weight for value, weight in valid) / weight_sum


def _score_from_ratio(ratio, max_score):
    if ratio is None:
        return None
    return round(ratio * max_score, 2)


def _period_start(period):
    now = timezone.localtime()
    if period == 'all':
        return None
    if period == 'year':
        return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    if period == 'quarter':
        quarter_start_month = ((now.month - 1) // 3) * 3 + 1
        return now.replace(month=quarter_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _period_label(period):
    if period == 'all':
        return "Barcha davr"
    if period == 'year':
        return "Joriy yil"
    if period == 'quarter':
        return "Joriy chorak"
    return "Joriy oy"


def _map_from_rows(rows, key_field, value_field):
    return {row[key_field]: row[value_field] for row in rows}


@login_required
def kpi_dashboard(request):
    period = (request.GET.get('period') or 'month').strip().lower()
    if period not in {'month', 'quarter', 'year', 'all'}:
        period = 'month'

    sector = (request.GET.get('sector') or '').strip()
    query = (request.GET.get('q') or '').strip()

    start_dt = _period_start(period)
    now = timezone.now()
    today = timezone.localdate()
    last_30_days = now - timedelta(days=30)

    leaders_qs = User.objects.filter(is_active=True, role='YETAKCHI').select_related('mahalla').order_by('full_name', 'username')
    if sector in {'1', '2', '3', '4'}:
        leaders_qs = leaders_qs.filter(sector=int(sector))
    if query:
        leaders_qs = leaders_qs.filter(
            Q(full_name__icontains=query) |
            Q(username__icontains=query) |
            Q(mahalla__name__icontains=query)
        )

    leaders = list(leaders_qs)
    leader_ids = [leader.id for leader in leaders]
    mahalla_ids = sorted({leader.mahalla_id for leader in leaders if leader.mahalla_id})

    total_yosh_by_mahalla = {}
    coverage_meeting_by_mahalla = {}
    unemployed_by_mahalla = {}
    assisted_by_mahalla = {}
    migration_total_by_mahalla = {}
    migration_recent_by_mahalla = {}
    otaliq_total_by_mahalla = {}
    otaliq_recent_by_mahalla = {}
    reyd_by_mahalla = {}
    five_events_by_mahalla = {}
    five_coverage_by_mahalla = {}

    task_total_by_leader = {}
    task_done_by_leader = {}
    task_overdue_by_leader = {}
    attendance_by_leader = {}
    discipline_by_leader = defaultdict(dict)

    if mahalla_ids:
        total_yosh_by_mahalla = _map_from_rows(
            Yosh.objects.filter(mahalla_id__in=mahalla_ids).values('mahalla_id').annotate(total=Count('id')),
            'mahalla_id',
            'total'
        )

        coverage_qs = Yosh.objects.filter(mahalla_id__in=mahalla_ids)
        if start_dt:
            coverage_qs = coverage_qs.filter(uchrashuvlar__meeting_date__gte=start_dt)
        else:
            coverage_qs = coverage_qs.filter(uchrashuvlar__isnull=False)
        coverage_meeting_by_mahalla = _map_from_rows(
            coverage_qs.values('mahalla_id').annotate(total=Count('id', distinct=True)),
            'mahalla_id',
            'total'
        )

        unemployed_by_mahalla = _map_from_rows(
            UnemployedYouth.objects.filter(yosh__mahalla_id__in=mahalla_ids)
            .values('yosh__mahalla_id').annotate(total=Count('id')),
            'yosh__mahalla_id',
            'total'
        )

        assisted_qs = UnemployedYouth.objects.filter(
            yosh__mahalla_id__in=mahalla_ids,
            assistance__provided=True,
        )
        if start_dt:
            assisted_qs = assisted_qs.filter(
                Q(assistance__date_provided__isnull=True) |
                Q(assistance__date_provided__gte=start_dt.date())
            )
        assisted_by_mahalla = _map_from_rows(
            assisted_qs.values('yosh__mahalla_id').annotate(total=Count('id')),
            'yosh__mahalla_id',
            'total'
        )

        migration_total_by_mahalla = _map_from_rows(
            MigrationYouth.objects.filter(yosh__mahalla_id__in=mahalla_ids)
            .values('yosh__mahalla_id').annotate(total=Count('id')),
            'yosh__mahalla_id',
            'total'
        )
        migration_recent_by_mahalla = _map_from_rows(
            MigrationYouth.objects.filter(
                yosh__mahalla_id__in=mahalla_ids,
                meetings__meeting_date__gte=last_30_days,
            ).values('yosh__mahalla_id').annotate(total=Count('id', distinct=True)),
            'yosh__mahalla_id',
            'total'
        )

        otaliq_total_by_mahalla = _map_from_rows(
            OtaliqYouth.objects.filter(yosh__mahalla_id__in=mahalla_ids)
            .values('yosh__mahalla_id').annotate(total=Count('id')),
            'yosh__mahalla_id',
            'total'
        )
        otaliq_recent_by_mahalla = _map_from_rows(
            OtaliqYouth.objects.filter(
                yosh__mahalla_id__in=mahalla_ids,
                meetings__meeting_date__gte=last_30_days,
            ).values('yosh__mahalla_id').annotate(total=Count('id', distinct=True)),
            'yosh__mahalla_id',
            'total'
        )

        reyd_qs = RaidEvent.objects.filter(mahalla_id__in=mahalla_ids)
        if start_dt:
            reyd_qs = reyd_qs.filter(event_date__gte=start_dt.date())
        reyd_by_mahalla = _map_from_rows(
            reyd_qs.values('mahalla_id').annotate(total=Count('id')),
            'mahalla_id',
            'total'
        )

        five_qs = FiveInitiativeEvent.objects.filter(mahalla_id__in=mahalla_ids)
        if start_dt:
            five_qs = five_qs.filter(event_date__gte=start_dt.date())
        for row in five_qs.values('mahalla_id').annotate(total_events=Count('id'), total_coverage=Sum('coverage')):
            five_events_by_mahalla[row['mahalla_id']] = row['total_events'] or 0
            five_coverage_by_mahalla[row['mahalla_id']] = row['total_coverage'] or 0

    if leader_ids:
        task_qs = Task.objects.filter(assigned_to_id__in=leader_ids)
        if start_dt:
            task_qs = task_qs.filter(created_at__gte=start_dt)
        task_total_by_leader = _map_from_rows(
            task_qs.values('assigned_to_id').annotate(total=Count('id')),
            'assigned_to_id',
            'total'
        )
        task_done_by_leader = _map_from_rows(
            task_qs.filter(status='YAKUNLANGAN').values('assigned_to_id').annotate(total=Count('id')),
            'assigned_to_id',
            'total'
        )
        task_overdue_by_leader = _map_from_rows(
            task_qs.filter(due_date__lt=now).exclude(status='YAKUNLANGAN').values('assigned_to_id').annotate(total=Count('id')),
            'assigned_to_id',
            'total'
        )

        attendance_qs = AttendanceRecord.objects.filter(leader_id__in=leader_ids, status__isnull=False)
        if start_dt:
            attendance_qs = attendance_qs.filter(session__session_date__gte=start_dt)
        for row in attendance_qs.values('leader_id').annotate(
            total=Count('id'),
            on_time=Count('id', filter=Q(status='ON_TIME')),
            excused=Count('id', filter=Q(status='EXCUSED')),
            late=Count('id', filter=Q(status='LATE')),
            unexcused=Count('id', filter=Q(status='UNEXCUSED')),
        ):
            attendance_by_leader[row['leader_id']] = row

        for row in DisciplineAction.objects.filter(employee_id__in=leader_ids, status='BOR').values('employee_id', 'action_type').annotate(total=Count('id')):
            discipline_by_leader[row['employee_id']][row['action_type']] = row['total']

    max_reyd = max(reyd_by_mahalla.values(), default=0)
    max_five_events = max(five_events_by_mahalla.values(), default=0)
    max_five_coverage = max(five_coverage_by_mahalla.values(), default=0)

    weights = {
        'coverage': 25,
        'employment': 30,
        'risk': 20,
        'execution': 15,
        'initiative': 10,
    }

    rows = []
    for leader in leaders:
        mahalla_id = leader.mahalla_id

        total_yosh = total_yosh_by_mahalla.get(mahalla_id, 0)
        covered_yosh = coverage_meeting_by_mahalla.get(mahalla_id, 0)
        coverage_ratio = _safe_ratio(covered_yosh, total_yosh)
        coverage_score = _score_from_ratio(coverage_ratio, weights['coverage'])

        unemployed_total = unemployed_by_mahalla.get(mahalla_id, 0)
        assisted_total = assisted_by_mahalla.get(mahalla_id, 0)
        employment_ratio = _safe_ratio(assisted_total, unemployed_total)
        employment_score = _score_from_ratio(employment_ratio, weights['employment'])

        migration_total = migration_total_by_mahalla.get(mahalla_id, 0)
        migration_recent = migration_recent_by_mahalla.get(mahalla_id, 0)
        migration_ratio = _safe_ratio(migration_recent, migration_total)

        otaliq_total = otaliq_total_by_mahalla.get(mahalla_id, 0)
        otaliq_recent = otaliq_recent_by_mahalla.get(mahalla_id, 0)
        otaliq_ratio = _safe_ratio(otaliq_recent, otaliq_total)

        risk_ratio = _weighted_mean([(migration_ratio, 0.5), (otaliq_ratio, 0.5)])
        risk_score = _score_from_ratio(risk_ratio, weights['risk'])

        task_total = task_total_by_leader.get(leader.id, 0)
        task_done = task_done_by_leader.get(leader.id, 0)
        task_overdue = task_overdue_by_leader.get(leader.id, 0)
        task_ratio = _safe_ratio(task_done, task_total)
        if task_ratio is not None and task_total > 0 and task_overdue > 0:
            overdue_ratio = task_overdue / task_total
            task_ratio = max(0.0, task_ratio - min(0.35, overdue_ratio * 0.35))

        attendance = attendance_by_leader.get(leader.id, {})
        attendance_total = attendance.get('total', 0) or 0
        if attendance_total > 0:
            attendance_ratio = (
                (attendance.get('on_time', 0) + attendance.get('excused', 0)) +
                (attendance.get('late', 0) * 0.6)
            ) / attendance_total
            if attendance_ratio > 1:
                attendance_ratio = 1.0
        else:
            attendance_ratio = None

        execution_base_ratio = _weighted_mean([(task_ratio, 0.6), (attendance_ratio, 0.4)])

        discipline_counts = discipline_by_leader.get(leader.id, {})
        discipline_penalty = (
            discipline_counts.get('OGOHLANTIRISH', 0) * 0.05 +
            discipline_counts.get('XAYFSAN', 0) * 0.09 +
            discipline_counts.get('ISH_HAQI_30', 0) * 0.13 +
            discipline_counts.get('ISH_HAQI_50', 0) * 0.18
        )
        discipline_penalty = min(discipline_penalty, 0.55)

        if execution_base_ratio is None:
            execution_ratio = max(0.0, 1 - discipline_penalty) if discipline_penalty > 0 else None
        else:
            execution_ratio = max(0.0, execution_base_ratio * (1 - discipline_penalty))
        execution_score = _score_from_ratio(execution_ratio, weights['execution'])

        reyd_count = reyd_by_mahalla.get(mahalla_id, 0)
        five_events_count = five_events_by_mahalla.get(mahalla_id, 0)
        five_coverage = five_coverage_by_mahalla.get(mahalla_id, 0)

        reyd_ratio = _safe_ratio(reyd_count, max_reyd) if max_reyd else None
        five_events_ratio = _safe_ratio(five_events_count, max_five_events) if max_five_events else None
        five_coverage_ratio = _safe_ratio(five_coverage, max_five_coverage) if max_five_coverage else None

        initiative_ratio = _weighted_mean([
            (reyd_ratio, 0.35),
            (five_events_ratio, 0.25),
            (five_coverage_ratio, 0.40),
        ])
        initiative_score = _score_from_ratio(initiative_ratio, weights['initiative'])

        scores = [
            ('coverage', coverage_score, weights['coverage']),
            ('employment', employment_score, weights['employment']),
            ('risk', risk_score, weights['risk']),
            ('execution', execution_score, weights['execution']),
            ('initiative', initiative_score, weights['initiative']),
        ]
        raw_total = sum(score for _, score, _ in scores if score is not None)
        available_weight = sum(weight for _, score, weight in scores if score is not None)
        total_score = round((raw_total / available_weight) * 100, 2) if available_weight else 0

        rows.append({
            'leader': leader,
            'mahalla_name': leader.mahalla.name if leader.mahalla else '-',
            'coverage_score': coverage_score,
            'employment_score': employment_score,
            'risk_score': risk_score,
            'execution_score': execution_score,
            'initiative_score': initiative_score,
            'total_score': total_score,
            'raw_total': round(raw_total, 2),
            'available_weight': available_weight,
            'coverage_ratio': round((coverage_ratio or 0) * 100, 1),
            'employment_ratio': round((employment_ratio or 0) * 100, 1),
            'migration_ratio': round((migration_ratio or 0) * 100, 1),
            'otaliq_ratio': round((otaliq_ratio or 0) * 100, 1),
            'task_ratio': round((task_ratio or 0) * 100, 1),
            'attendance_ratio': round((attendance_ratio or 0) * 100, 1),
            'discipline_penalty': round(discipline_penalty * 100, 1),
            'discipline_count': sum(discipline_counts.values()),
        })

    rows.sort(key=lambda item: (item['total_score'], item['available_weight'], item['raw_total']), reverse=True)
    for index, row in enumerate(rows, start=1):
        row['rank'] = index

    top_row = rows[0] if rows else None
    avg_total = round(sum(row['total_score'] for row in rows) / len(rows), 1) if rows else 0
    high_result_count = sum(1 for row in rows if row['total_score'] >= 80)

    direction_avg = {
        'coverage': round(sum((row['coverage_score'] or 0) for row in rows) / len(rows), 2) if rows else 0,
        'employment': round(sum((row['employment_score'] or 0) for row in rows) / len(rows), 2) if rows else 0,
        'risk': round(sum((row['risk_score'] or 0) for row in rows) / len(rows), 2) if rows else 0,
        'execution': round(sum((row['execution_score'] or 0) for row in rows) / len(rows), 2) if rows else 0,
        'initiative': round(sum((row['initiative_score'] or 0) for row in rows) / len(rows), 2) if rows else 0,
    }
    best_direction_key = max(direction_avg, key=direction_avg.get) if rows else 'coverage'
    direction_labels = {
        'coverage': "Qamrov",
        'employment': "Bandlik",
        'risk': "Xavf guruhlari",
        'execution': "Ijro-intizom",
        'initiative': "Tadbirlar",
    }

    period_range = (
        f"{start_dt.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')}"
        if start_dt else
        "Barcha vaqt bo'yicha"
    )

    context = {
        'rows': rows,
        'top_row': top_row,
        'avg_total': avg_total,
        'high_result_count': high_result_count,
        'leaders_count': len(rows),
        'direction_avg': direction_avg,
        'best_direction': direction_labels[best_direction_key],
        'best_direction_score': direction_avg.get(best_direction_key, 0),
        'selected_period': period,
        'selected_sector': sector,
        'q': query,
        'period_label': _period_label(period),
        'period_range': period_range,
    }
    return render(request, 'kpi/dashboard.html', context)

@login_required
def yosh_list(request):
    user = request.user
    mahallas = None

    if _is_management_user(user):
        qs = Yosh.objects.all().order_by('fullname')
        mahallas = Mahalla.objects.all().order_by('name')
        
        mahalla_id = request.GET.get('mahalla')
        if mahalla_id:
            qs = qs.filter(mahalla_id=mahalla_id)
    else:
        qs = Yosh.objects.filter(mahalla=user.mahalla).order_by('fullname')

    # Search
    q = request.GET.get('q')
    if q:
        q = q.strip()
        use_wildcard = ("*" in q) or ("?" in q)
        if use_wildcard:
            # ? -> bitta belgi, * -> bir nechta belgi (FIO uchun)
            pattern = re.escape(q).replace(r"\*", ".*").replace(r"\?", ".")
            fullname_q = Q(fullname__iregex=f".*{pattern}.*")
            q_plain = q.replace("*", "").replace("?", "").strip()
        else:
            fullname_q = Q(fullname__icontains=q)
            q_plain = q

        full_q = fullname_q
        if q_plain:
            full_q = (
                full_q |
                Q(phone_number__icontains=q_plain) |
                Q(passport_number__icontains=q_plain) |
                Q(jshshir__icontains=q_plain) |
                Q(birth_date__icontains=q_plain)
            )

        qs = qs.filter(full_q)

    # Annotate status (faqat umumiy yoshlar suhbatlari)
    qs = qs.select_related('mahalla', 'unemployed_profile', 'unemployed_profile__assistance').prefetch_related('mahalla__leaders').annotate(
        meeting_count=Count('uchrashuvlar', distinct=True),
    ).annotate(
        has_meeting=Case(
            When(Q(meeting_count__gt=0), then=True),
            default=False,
            output_field=BooleanField(),
        )
    )

    # Filter by status
    status = request.GET.get('status')
    if status == 'bor':
        qs = qs.filter(meeting_count__gt=0)
    elif status == 'yoq':
        qs = qs.filter(meeting_count=0)

    # Per Page logic
    per_page = request.GET.get('per_page', '20')
    if per_page not in ['10', '20', '50', '100', '200']:
        per_page = '20'
    
    paginator = Paginator(qs, int(per_page))
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'per_page': per_page,
        'mahallas': mahallas,
        'selected_mahalla': int(request.GET.get('mahalla')) if request.GET.get('mahalla') and request.GET.get('mahalla').isdigit() else None,
        'selected_status': request.GET.get('status'),
    }
    return render(request, 'list.html', context)

@login_required
def yosh_detail(request, pk=None):
    user = request.user
    if pk:
        yosh = get_object_or_404(Yosh, pk=pk)
        # Check permission: if leader, must be his mahalla
        if not _is_management_user(user) and yosh.mahalla != user.mahalla:
            return render(request, '403.html', {'message': "Sizga bu anketa huquqi berilmagan"})
    else:
        yosh = None

    if request.method == 'POST':
        form = YoshForm(request.POST, request.FILES, instance=yosh, user=user)
        if form.is_valid():
            new_yosh = form.save(commit=False)
            if not _is_management_user(user):
                new_yosh.mahalla = user.mahalla
            else:
                # Superadmin must pick mahalla from form
                new_yosh.mahalla = form.cleaned_data.get('mahalla')
            # If superadmin creating, mahalla must be required. 
            # Logic omission: YoshForm excludes mahalla, so SuperAdmin creating creates NULL? 
            # I must handle this. For now assume SuperAdmin edits existing or I add Mahalla field for Admin.
            # Fix: If superadmin and new, assign a Default or Form should include it.
            # Prompt says "Super Admin ... 46 ta mahallani qo'shish ... Har qanday yosh anketasini tahrirlash".
            # Doesn't explicitly say Creating Youth for *specific* mahalla by Admin, but implied.
            # I'll assume Admin manages existing mostly, or I fix Form to include Mahalla if Admin.
            
            # For simplicity: If Admin creates, I'll pick first mahalla or error. 
            # better: add Mahalla to form if admin. 
            # But let's save what we have.
            if not new_yosh.mahalla:
                 messages.error(request, "Mahalla tanlanishi shart.")
                 return render(request, 'form.html', {'form': form, 'yosh': yosh, 'meetings': meetings})

            new_yosh.save()
            
            # Handle conversation
            text = form.cleaned_data.get('conversation_text')
            photo = form.cleaned_data.get('conversation_photo')
            if text:
                Uchrashuv.objects.create(
                    yosh=new_yosh,
                    yetakchi=user,
                    meeting_date=timezone.now(),
                    conversation_text=text,
                    photo=photo
                )
            return redirect('yosh_list')
    else:
        form = YoshForm(instance=yosh, user=user)

    meetings = yosh.uchrashuvlar.all().order_by('-meeting_date') if yosh else []
    readonly = request.GET.get('readonly') == 'true'
    
    return render(request, 'form.html', {
        'form': form, 
        'yosh': yosh, 
        'meetings': meetings,
        'readonly': readonly
    })

@login_required
def meeting_edit(request, pk):
    meeting = get_object_or_404(Uchrashuv, pk=pk)
    user = request.user
    if not _is_management_user(user) and meeting.yetakchi != user and meeting.yosh.mahalla != user.mahalla:
         return redirect('dashboard') # Access denied logic

    if request.method == 'POST':
        form = UchrashuvForm(request.POST, request.FILES, instance=meeting)
        if form.is_valid():
            form.save()
            return redirect('yosh_detail', pk=meeting.yosh.pk)
    else:
        form = UchrashuvForm(instance=meeting)
    
    return render(request, 'meeting_form.html', {'form': form, 'meeting': meeting})

def info_view(request):
    return render(request, 'info.html')


@login_required
def user_profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Anketa ma'lumotlari saqlandi.")
            return redirect('user_profile')
        messages.error(request, "Iltimos, formadagi xatolarni to'g'rilang.")
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, 'profile.html', {'form': form})


@login_required
def user_list(request):
    if not _is_management_user(request.user):
        messages.error(request, "Bu bo'lim faqat Super Admin yoki Rahbar uchun.")
        return redirect('dashboard')

    users = User.objects.select_related('mahalla').all().order_by('full_name', 'username')

    q = (request.GET.get('q') or '').strip()
    role = (request.GET.get('role') or '').strip()

    if q:
        users = users.filter(
            Q(full_name__icontains=q) |
            Q(username__icontains=q) |
            Q(pinfl__icontains=q) |
            Q(phone_number__icontains=q) |
            Q(mahalla__name__icontains=q)
        )
    if role in {'SUPER_ADMIN', 'RAHBAR', 'YETAKCHI'}:
        users = users.filter(role=role)

    context = {
        'users': users,
        'q': q,
        'selected_role': role,
    }
    return render(request, 'users/list.html', context)


@login_required
def mega_projects(request):
    projects = [
        {
            "key": "mutolaa",
            "name": "Mutolaa",
            "icon": "bi-book",
            "accent": "var(--mega-blue)",
            "status": "API ulanmagan",
            "updated": "—",
            "logo_static": "img/mutolaa_logo.png",
        },
        {
            "key": "ustoz-ai",
            "name": "Ustoz AI",
            "icon": "bi-robot",
            "accent": "var(--mega-green)",
            "status": "API ulanmagan",
            "updated": "—",
            "logo": "https://ustoz.ai/icons/logo-ustozai.svg",
        },
        {
            "key": "uzchess",
            "name": "UzChess",
            "icon": "bi-diagram-3",
            "accent": "var(--mega-orange)",
            "status": "API ulanmagan",
            "updated": "—",
        },
        {
            "key": "qizlar-akademiyasi",
            "name": "Qizlar akademiyasi",
            "icon": "bi-gender-female",
            "accent": "var(--mega-pink)",
            "status": "API ulanmagan",
            "updated": "—",
        },
    ]
    return render(request, 'mega_loyihalar/mega_projects.html', {"projects": projects})


@login_required
def mega_mutolaa(request):
    latest_snapshot = (
        MutolaaStatSnapshot.objects.order_by("-snapshot_date", "-fetched_at").first()
    )
    mahallas = list(Mahalla.objects.all().order_by("name"))
    youth_counts = {
        item["mahalla"]: item["count"]
        for item in Yosh.objects.values("mahalla").annotate(count=Count("id"))
    }
    columns, rows, total_row = build_table(latest_snapshot, mahallas=mahallas, youth_counts=youth_counts)
    return render(request, 'mega_loyihalar/mutolaa.html', {
        "snapshot": latest_snapshot,
        "table_columns": columns,
        "table_rows": rows,
        "total_row": total_row,
        "can_refresh": _is_management_user(request.user),
    })


@login_required
def mega_ustoz_ai(request):
    latest_snapshot = (
        UstozAiStatSnapshot.objects.order_by("-snapshot_date", "-fetched_at").first()
    )
    mahallas = list(Mahalla.objects.all().order_by("name"))
    youth_counts = {
        item["mahalla"]: item["count"]
        for item in Yosh.objects.values("mahalla").annotate(count=Count("id"))
    }
    columns, rows, total_row = build_ustoz_table(latest_snapshot, mahallas=mahallas, youth_counts=youth_counts)

    return render(request, 'mega_loyihalar/ustoz_ai.html', {
        "snapshot": latest_snapshot,
        "table_columns": columns,
        "table_rows": rows,
        "total_row": total_row,
        "can_refresh": _is_management_user(request.user),
    })


@login_required
@require_POST
def mega_ustoz_ai_refresh(request):
    snapshot, error = fetch_and_store_ustoz_ai_snapshot()
    if error:
        messages.error(request, f"Ustoz AI statistikasi yangilanmadi: {error}")
    else:
        messages.success(request, "Ustoz AI statistikasi yangilandi.")
    return redirect('mega_ustoz_ai')


@login_required
def mega_uzchess(request):
    latest_snapshot = (
        UzchessStatSnapshot.objects.order_by("-snapshot_date", "-fetched_at").first()
    )
    mahallas = list(Mahalla.objects.all().order_by("name"))
    youth_counts = {
        item["mahalla"]: item["count"]
        for item in Yosh.objects.values("mahalla").annotate(count=Count("id"))
    }
    columns, rows, total_row = build_uzchess_table(latest_snapshot, mahallas=mahallas, youth_counts=youth_counts)

    return render(request, 'mega_loyihalar/uzchess.html', {
        "snapshot": latest_snapshot,
        "table_columns": columns,
        "table_rows": rows,
        "total_row": total_row,
        "can_refresh": _is_management_user(request.user),
    })


@login_required
@require_POST
def mega_uzchess_refresh(request):
    snapshot, error = fetch_and_store_uzchess_snapshot()
    if error:
        messages.error(request, f"UzChess statistikasi yangilanmadi: {error}")
    else:
        messages.success(request, "UzChess statistikasi yangilandi.")
    return redirect('mega_uzchess')


@login_required
def mega_girls_academy(request):
    latest_snapshot = (
        QizlarAkademiyasiStatSnapshot.objects.order_by("-snapshot_date", "-fetched_at").first()
    )
    mahallas = list(Mahalla.objects.all().order_by("name"))
    youth_counts = {
        item["mahalla"]: item["count"]
        for item in Yosh.objects.values("mahalla").annotate(count=Count("id"))
    }
    columns, rows, total_row = build_qizlar_table(latest_snapshot, mahallas=mahallas, youth_counts=youth_counts)

    return render(request, 'mega_loyihalar/qizlar_akademiyasi.html', {
        "snapshot": latest_snapshot,
        "table_columns": columns,
        "table_rows": rows,
        "total_row": total_row,
        "can_refresh": _is_management_user(request.user),
    })


@login_required
@require_POST
def mega_girls_academy_refresh(request):
    if not _is_management_user(request.user):
        messages.error(request, "Yangilash faqat adminlar uchun ruxsat etilgan.")
        return redirect('mega_girls_academy')
    snapshot, error = fetch_and_store_qizlar_snapshot()
    if error:
        messages.error(request, f"Qizlar akademiyasi statistikasi yangilanmadi: {error}")
    else:
        messages.success(request, "Qizlar akademiyasi statistikasi yangilandi.")
    return redirect('mega_girls_academy')


@login_required
@require_POST
def mega_mutolaa_refresh(request):
    snapshot, error = fetch_and_store_mutolaa_snapshot()
    if error:
        messages.error(request, f"Mutolaa statistikasi yangilanmadi: {error}")
    else:
        messages.success(request, "Mutolaa statistikasi yangilandi.")
    return redirect('mega_mutolaa')
