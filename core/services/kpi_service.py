from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from django.db.models import Count, Q, Sum
from django.utils import timezone

from beshtashabbus.models import FiveInitiativeEvent
from intizom_jazo.models import DisciplineAction
from ishsiz_yoshlar.models import Task, UnemployedYouth
from migratsiya.models import MigrationYouth
from otaliq.models import OtaliqYouth
from reyd.models import RaidEvent
from yoqlama.models import AttendanceRecord

from core.models import LeaderKpiSnapshot, User, Yosh


DEFAULT_WEIGHTS = {
    'coverage': 25,
    'employment': 30,
    'risk': 20,
    'execution': 15,
    'initiative': 10,
}


def _as_date(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            return timezone.localtime(value).date()
        return value.date()
    raise TypeError("from_date/to_date date yoki datetime bo'lishi kerak.")


def _period_bounds(from_date: Optional[date], to_date: Optional[date]) -> Tuple[Optional[datetime], Optional[datetime]]:
    if from_date is None and to_date is None:
        return None, None

    from_part = _as_date(from_date) if from_date is not None else None
    to_part = _as_date(to_date) if to_date is not None else None

    if from_part and to_part and from_part > to_part:
        raise ValueError("from_date to_date dan katta bo'lishi mumkin emas.")

    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(from_part, time.min), tz) if from_part else None
    end_dt = timezone.make_aware(datetime.combine(to_part, time.max), tz) if to_part else None
    return start_dt, end_dt


def _filter_dt_range(queryset, field_name: str, start_dt: Optional[datetime], end_dt: Optional[datetime]):
    if start_dt:
        queryset = queryset.filter(**{f'{field_name}__gte': start_dt})
    if end_dt:
        queryset = queryset.filter(**{f'{field_name}__lte': end_dt})
    return queryset


def _filter_date_range(queryset, field_name: str, from_date: Optional[date], to_date: Optional[date]):
    if from_date:
        queryset = queryset.filter(**{f'{field_name}__gte': from_date})
    if to_date:
        queryset = queryset.filter(**{f'{field_name}__lte': to_date})
    return queryset


def _safe_ratio(numerator: float, denominator: float) -> Optional[float]:
    if not denominator:
        return None
    ratio = numerator / denominator
    if ratio < 0:
        return 0.0
    if ratio > 1:
        return 1.0
    return ratio


def _weighted_mean(weighted_values: Iterable[Tuple[Optional[float], float]]) -> Optional[float]:
    valid = [(value, weight) for value, weight in weighted_values if value is not None]
    if not valid:
        return None
    weight_sum = sum(weight for _, weight in valid)
    if not weight_sum:
        return None
    return sum(value * weight for value, weight in valid) / weight_sum


def _score_from_ratio(ratio: Optional[float], max_score: int) -> Optional[float]:
    if ratio is None:
        return None
    return round(ratio * max_score, 2)


def _map_from_rows(rows: Iterable[dict], key_field: str, value_field: str) -> Dict:
    return {row[key_field]: row[value_field] for row in rows}


def _normalize_leaders(leaders: Iterable[User]) -> List[User]:
    if hasattr(leaders, 'select_related'):
        leaders = leaders.select_related('mahalla')
    return list(leaders)


def build_kpi_rows(
    leaders: Iterable[User],
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    weights: Optional[dict] = None,
) -> List[dict]:
    leaders = _normalize_leaders(leaders)
    if not leaders:
        return []

    current_weights = dict(DEFAULT_WEIGHTS)
    if weights:
        current_weights.update(weights)

    start_dt, end_dt = _period_bounds(from_date, to_date)
    range_from = _as_date(from_date) if from_date is not None else None
    range_to = _as_date(to_date) if to_date is not None else None

    now = timezone.now()
    analysis_end_dt = end_dt or now
    last_30_days_start = analysis_end_dt - timedelta(days=30)

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
            'total',
        )

        coverage_qs = Yosh.objects.filter(mahalla_id__in=mahalla_ids, uchrashuvlar__isnull=False)
        coverage_qs = _filter_dt_range(coverage_qs, 'uchrashuvlar__meeting_date', start_dt, end_dt)
        coverage_meeting_by_mahalla = _map_from_rows(
            coverage_qs.values('mahalla_id').annotate(total=Count('id', distinct=True)),
            'mahalla_id',
            'total',
        )

        unemployed_by_mahalla = _map_from_rows(
            UnemployedYouth.objects.filter(yosh__mahalla_id__in=mahalla_ids)
            .values('yosh__mahalla_id').annotate(total=Count('id')),
            'yosh__mahalla_id',
            'total',
        )

        assisted_qs = UnemployedYouth.objects.filter(
            yosh__mahalla_id__in=mahalla_ids,
            assistance__provided=True,
        )
        if range_from or range_to:
            date_filter = Q(assistance__date_provided__isnull=True)
            if range_from and range_to:
                date_filter |= Q(assistance__date_provided__range=(range_from, range_to))
            elif range_from:
                date_filter |= Q(assistance__date_provided__gte=range_from)
            elif range_to:
                date_filter |= Q(assistance__date_provided__lte=range_to)
            assisted_qs = assisted_qs.filter(date_filter)

        assisted_by_mahalla = _map_from_rows(
            assisted_qs.values('yosh__mahalla_id').annotate(total=Count('id')),
            'yosh__mahalla_id',
            'total',
        )

        migration_total_by_mahalla = _map_from_rows(
            MigrationYouth.objects.filter(yosh__mahalla_id__in=mahalla_ids)
            .values('yosh__mahalla_id').annotate(total=Count('id')),
            'yosh__mahalla_id',
            'total',
        )
        migration_recent_qs = MigrationYouth.objects.filter(
            yosh__mahalla_id__in=mahalla_ids,
            meetings__meeting_date__gte=last_30_days_start,
            meetings__meeting_date__lte=analysis_end_dt,
        )
        migration_recent_by_mahalla = _map_from_rows(
            migration_recent_qs.values('yosh__mahalla_id').annotate(total=Count('id', distinct=True)),
            'yosh__mahalla_id',
            'total',
        )

        otaliq_total_by_mahalla = _map_from_rows(
            OtaliqYouth.objects.filter(yosh__mahalla_id__in=mahalla_ids)
            .values('yosh__mahalla_id').annotate(total=Count('id')),
            'yosh__mahalla_id',
            'total',
        )
        otaliq_recent_qs = OtaliqYouth.objects.filter(
            yosh__mahalla_id__in=mahalla_ids,
            meetings__meeting_date__gte=last_30_days_start,
            meetings__meeting_date__lte=analysis_end_dt,
        )
        otaliq_recent_by_mahalla = _map_from_rows(
            otaliq_recent_qs.values('yosh__mahalla_id').annotate(total=Count('id', distinct=True)),
            'yosh__mahalla_id',
            'total',
        )

        reyd_qs = RaidEvent.objects.filter(mahalla_id__in=mahalla_ids)
        reyd_qs = _filter_date_range(reyd_qs, 'event_date', range_from, range_to)
        reyd_by_mahalla = _map_from_rows(
            reyd_qs.values('mahalla_id').annotate(total=Count('id')),
            'mahalla_id',
            'total',
        )

        five_qs = FiveInitiativeEvent.objects.filter(mahalla_id__in=mahalla_ids)
        five_qs = _filter_date_range(five_qs, 'event_date', range_from, range_to)
        for row in five_qs.values('mahalla_id').annotate(total_events=Count('id'), total_coverage=Sum('coverage')):
            five_events_by_mahalla[row['mahalla_id']] = row['total_events'] or 0
            five_coverage_by_mahalla[row['mahalla_id']] = row['total_coverage'] or 0

    if leader_ids:
        task_qs = Task.objects.filter(assigned_to_id__in=leader_ids)
        task_qs = _filter_dt_range(task_qs, 'created_at', start_dt, end_dt)
        task_total_by_leader = _map_from_rows(
            task_qs.values('assigned_to_id').annotate(total=Count('id')),
            'assigned_to_id',
            'total',
        )
        task_done_by_leader = _map_from_rows(
            task_qs.filter(status='YAKUNLANGAN').values('assigned_to_id').annotate(total=Count('id')),
            'assigned_to_id',
            'total',
        )
        task_overdue_by_leader = _map_from_rows(
            task_qs.filter(due_date__lt=analysis_end_dt).exclude(status='YAKUNLANGAN')
            .values('assigned_to_id').annotate(total=Count('id')),
            'assigned_to_id',
            'total',
        )

        attendance_qs = AttendanceRecord.objects.filter(leader_id__in=leader_ids, status__isnull=False)
        attendance_qs = _filter_dt_range(attendance_qs, 'session__session_date', start_dt, end_dt)
        for row in attendance_qs.values('leader_id').annotate(
            total=Count('id'),
            on_time=Count('id', filter=Q(status='ON_TIME')),
            excused=Count('id', filter=Q(status='EXCUSED')),
            late=Count('id', filter=Q(status='LATE')),
            unexcused=Count('id', filter=Q(status='UNEXCUSED')),
        ):
            attendance_by_leader[row['leader_id']] = row

        discipline_qs = DisciplineAction.objects.filter(employee_id__in=leader_ids, status='BOR')
        if range_to:
            discipline_qs = discipline_qs.filter(action_date__lte=range_to)
        for row in discipline_qs.values('employee_id', 'action_type').annotate(total=Count('id')):
            discipline_by_leader[row['employee_id']][row['action_type']] = row['total']

    max_reyd = max(reyd_by_mahalla.values(), default=0)
    max_five_events = max(five_events_by_mahalla.values(), default=0)
    max_five_coverage = max(five_coverage_by_mahalla.values(), default=0)

    rows = []
    for leader in leaders:
        mahalla_id = leader.mahalla_id

        total_yosh = total_yosh_by_mahalla.get(mahalla_id, 0)
        covered_yosh = coverage_meeting_by_mahalla.get(mahalla_id, 0)
        coverage_ratio = _safe_ratio(covered_yosh, total_yosh)
        coverage_score = _score_from_ratio(coverage_ratio, current_weights['coverage'])

        unemployed_total = unemployed_by_mahalla.get(mahalla_id, 0)
        assisted_total = assisted_by_mahalla.get(mahalla_id, 0)
        employment_ratio = _safe_ratio(assisted_total, unemployed_total)
        employment_score = _score_from_ratio(employment_ratio, current_weights['employment'])

        migration_total = migration_total_by_mahalla.get(mahalla_id, 0)
        migration_recent = migration_recent_by_mahalla.get(mahalla_id, 0)
        migration_ratio = _safe_ratio(migration_recent, migration_total)

        otaliq_total = otaliq_total_by_mahalla.get(mahalla_id, 0)
        otaliq_recent = otaliq_recent_by_mahalla.get(mahalla_id, 0)
        otaliq_ratio = _safe_ratio(otaliq_recent, otaliq_total)

        risk_ratio = _weighted_mean([(migration_ratio, 0.5), (otaliq_ratio, 0.5)])
        risk_score = _score_from_ratio(risk_ratio, current_weights['risk'])

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
        execution_score = _score_from_ratio(execution_ratio, current_weights['execution'])

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
        initiative_score = _score_from_ratio(initiative_ratio, current_weights['initiative'])

        scores = [
            ('coverage', coverage_score, current_weights['coverage']),
            ('employment', employment_score, current_weights['employment']),
            ('risk', risk_score, current_weights['risk']),
            ('execution', execution_score, current_weights['execution']),
            ('initiative', initiative_score, current_weights['initiative']),
        ]
        raw_total = sum(score for _, score, _ in scores if score is not None)
        available_weight = sum(weight for _, score, weight in scores if score is not None)
        total_score = round((raw_total / available_weight) * 100, 2) if available_weight else 0

        block_scores = {
            'coverage': coverage_score,
            'employment': employment_score,
            'risk': risk_score,
            'execution': execution_score,
            'initiative': initiative_score,
        }
        debug_json = {
            'period': {
                'from': str(range_from) if range_from else None,
                'to': str(range_to) if range_to else None,
            },
            'weights': current_weights,
            'counts': {
                'total_yosh': total_yosh,
                'covered_yosh': covered_yosh,
                'unemployed_total': unemployed_total,
                'assisted_total': assisted_total,
                'migration_total': migration_total,
                'migration_recent': migration_recent,
                'otaliq_total': otaliq_total,
                'otaliq_recent': otaliq_recent,
                'task_total': task_total,
                'task_done': task_done,
                'task_overdue': task_overdue,
                'attendance_total': attendance_total,
                'reyd_count': reyd_count,
                'five_events_count': five_events_count,
                'five_coverage': five_coverage,
            },
            'ratios': {
                'coverage': coverage_ratio,
                'employment': employment_ratio,
                'risk': risk_ratio,
                'task': task_ratio,
                'attendance': attendance_ratio,
                'execution': execution_ratio,
                'initiative': initiative_ratio,
            },
            'discipline_penalty': discipline_penalty,
            'discipline_counts': discipline_counts,
            'raw_total': round(raw_total, 2),
            'available_weight': available_weight,
        }

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
            'coverage_warning': available_weight < 100,
            'coverage_ratio': round((coverage_ratio or 0) * 100, 1),
            'employment_ratio': round((employment_ratio or 0) * 100, 1),
            'migration_ratio': round((migration_ratio or 0) * 100, 1),
            'otaliq_ratio': round((otaliq_ratio or 0) * 100, 1),
            'task_ratio': round((task_ratio or 0) * 100, 1),
            'attendance_ratio': round((attendance_ratio or 0) * 100, 1),
            'discipline_penalty': round(discipline_penalty * 100, 1),
            'discipline_count': sum(discipline_counts.values()),
            'block_scores': block_scores,
            'debug_json': debug_json,
        })

    rows.sort(key=lambda item: (item['total_score'], item['available_weight'], item['raw_total']), reverse=True)
    for index, row in enumerate(rows, start=1):
        row['rank'] = index
    return rows


def compute_leader_kpi(user: User, from_date: date, to_date: date) -> dict:
    if user is None or not getattr(user, 'pk', None):
        raise TypeError("user parametri saqlangan foydalanuvchi bo'lishi kerak.")

    start_date = _as_date(from_date)
    end_date = _as_date(to_date)
    if start_date > end_date:
        raise ValueError("from_date to_date dan katta bo'lishi mumkin emas.")

    rows = build_kpi_rows([user], from_date=start_date, to_date=end_date)
    if not rows:
        block_scores = {key: None for key in DEFAULT_WEIGHTS.keys()}
        return {
            'user': user,
            'date_from': start_date,
            'date_to': end_date,
            'block_scores': block_scores,
            'total_score': 0.0,
            'debug_json': {
                'error': 'KPI hisoblash uchun maʼlumot topilmadi.',
                'period': {'from': str(start_date), 'to': str(end_date)},
            },
        }

    row = rows[0]
    return {
        'user': user,
        'date_from': start_date,
        'date_to': end_date,
        'block_scores': row['block_scores'],
        'total_score': row['total_score'],
        'debug_json': row['debug_json'],
        'row': row,
    }


def upsert_leader_kpi_snapshot(user: User, from_date: date, to_date: date) -> LeaderKpiSnapshot:
    result = compute_leader_kpi(user, from_date, to_date)
    snapshot, _ = LeaderKpiSnapshot.objects.update_or_create(
        user=user,
        date_from=result['date_from'],
        date_to=result['date_to'],
        defaults={
            'block_scores': result['block_scores'],
            'total_score': result['total_score'],
            'debug_json': result['debug_json'],
        },
    )
    return snapshot


def compute_and_store_kpi_snapshots(users: Iterable[User], from_date: date, to_date: date) -> List[LeaderKpiSnapshot]:
    snapshots = []
    for user in users:
        snapshots.append(upsert_leader_kpi_snapshot(user, from_date, to_date))
    return snapshots
