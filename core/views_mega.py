import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import (
    Mahalla,
    MutolaaStatSnapshot,
    QizlarAkademiyasiStatSnapshot,
    UstozAiStatSnapshot,
    UzchessStatSnapshot,
    Yosh,
)
from .mutolaa import build_table, fetch_and_store_mutolaa_snapshot
from .qizlar_akademiyasi import build_table as build_qizlar_table
from .qizlar_akademiyasi import fetch_and_store_qizlar_snapshot
from .ustoz_ai import build_table as build_ustoz_table
from .ustoz_ai import fetch_and_store_ustoz_ai_snapshot
from .uzchess import build_table as build_uzchess_table
from .uzchess import fetch_and_store_uzchess_snapshot
from .view_helpers import is_management_user
from .view_helpers import normalize_sort_params


def _to_number(value):
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text or text in {"-", "—", "–"}:
            return None
        if not re.fullmatch(r"[-+]?\d[\d\s,]*(?:\.\d+)?%?", text):
            return None
        normalized = re.sub(r"[\s,%]", "", text)
        if normalized and re.fullmatch(r"-?\d+(?:\.\d+)?", normalized):
            return float(normalized)
    return None


def _format_number(value):
    if value is None:
        return 0
    if abs(value - round(value)) < 1e-9:
        return int(round(value))
    return round(value, 2)


def _build_mega_view_context(request, snapshot_model, table_builder, compare_fields):
    snapshot_history = list(snapshot_model.objects.order_by("-snapshot_date", "-fetched_at")[:50])
    latest_snapshot = snapshot_history[0] if snapshot_history else None

    mahallas = list(Mahalla.objects.all().order_by("name"))
    youth_counts = {
        item["mahalla"]: item["count"]
        for item in Yosh.objects.values("mahalla").annotate(count=Count("id"))
    }

    columns, rows, total_row = table_builder(latest_snapshot, mahallas=mahallas, youth_counts=youth_counts)

    allowed_sort_fields = set(columns) | {"mahalla_name"}
    sort_field, sort_direction = normalize_sort_params(request, allowed_sort_fields, "mahalla_name")

    def _row_sort_value(row):
        value = row.get(sort_field)
        numeric_value = _to_number(value)
        if numeric_value is not None:
            return numeric_value
        return ("" if value is None else str(value)).casefold()

    if rows and sort_field in allowed_sort_fields:
        rows = sorted(rows, key=_row_sort_value, reverse=sort_direction == "desc")

    # Extract percent map from table rows for polygon visualization
    percent_map = {}
    for row in rows:
        mahalla_name = row.get('mahalla_name')
        percent = row.get('users_ratio_percent', 0)
        if mahalla_name:
            percent_map[mahalla_name] = percent

    context = {
        "snapshot": latest_snapshot,
        "snapshot_history": snapshot_history,
        "table_columns": columns,
        "table_rows": rows,
        "total_row": total_row,
        "can_refresh": is_management_user(request.user),
        "compare_enabled": False,
        "compare_rows": [],
        "compare_summary": [],
        "compare_left_snapshot": None,
        "compare_right_snapshot": None,
        "selected_left_snapshot_id": None,
        "selected_right_snapshot_id": None,
        "mega_sort_field": sort_field,
        "mega_sort_direction": sort_direction,
        # NEW: Add polygon data
        "mahalla_percent_map": percent_map,
        "mahalla_names": list(Mahalla.objects.values('id', 'name')),
    }

    if len(snapshot_history) >= 2:
        context["selected_left_snapshot_id"] = str(snapshot_history[0].id)
        context["selected_right_snapshot_id"] = str(snapshot_history[1].id)

    if request.GET.get("compare") != "1":
        return context

    left_id = request.GET.get("left_snapshot_id")
    right_id = request.GET.get("right_snapshot_id")
    context["selected_left_snapshot_id"] = left_id
    context["selected_right_snapshot_id"] = right_id

    if not (left_id and right_id):
        return context

    left_snapshot = snapshot_model.objects.filter(pk=left_id).first()
    right_snapshot = snapshot_model.objects.filter(pk=right_id).first()
    if not left_snapshot or not right_snapshot or left_snapshot.pk == right_snapshot.pk:
        return context

    _, left_rows, left_total = table_builder(left_snapshot, mahallas=mahallas, youth_counts=youth_counts)
    _, right_rows, right_total = table_builder(right_snapshot, mahallas=mahallas, youth_counts=youth_counts)
    left_map = {row.get("mahalla_name"): row for row in left_rows}
    right_map = {row.get("mahalla_name"): row for row in right_rows}
    mahalla_names = sorted(set(left_map.keys()) | set(right_map.keys()))

    compare_rows = []
    for name in mahalla_names:
        left_row = left_map.get(name, {})
        right_row = right_map.get(name, {})
        cells = []
        has_changes = False
        for field_key, _field_label in compare_fields:
            old_val = _to_number(left_row.get(field_key))
            new_val = _to_number(right_row.get(field_key))
            old_val = 0.0 if old_val is None else old_val
            new_val = 0.0 if new_val is None else new_val
            delta = new_val - old_val
            if abs(delta) > 1e-9:
                has_changes = True
            if delta > 0:
                delta_class = "text-success fw-semibold"
            elif delta < 0:
                delta_class = "text-danger fw-semibold"
            else:
                delta_class = "text-muted"
            cells.append(
                {
                    "old": _format_number(old_val),
                    "new": _format_number(new_val),
                    "delta": _format_number(delta),
                    "delta_class": delta_class,
                }
            )
        compare_rows.append(
            {
                "mahalla_name": name,
                "cells": cells,
                "has_changes": has_changes,
            }
        )

    compare_rows.sort(
        key=lambda row: (
            not row["has_changes"],
            -max(abs(cell["delta"]) for cell in row["cells"]) if row["cells"] else 0,
            row["mahalla_name"],
        )
    )

    summary = []
    left_total = left_total or {}
    right_total = right_total or {}
    for field_key, field_label in compare_fields:
        old_total = _to_number(left_total.get(field_key)) or 0.0
        new_total = _to_number(right_total.get(field_key)) or 0.0
        delta_total = new_total - old_total
        if delta_total > 0:
            delta_class = "text-success fw-semibold"
        elif delta_total < 0:
            delta_class = "text-danger fw-semibold"
        else:
            delta_class = "text-muted"
        summary.append(
            {
                "label": field_label,
                "old": _format_number(old_total),
                "new": _format_number(new_total),
                "delta": _format_number(delta_total),
                "delta_class": delta_class,
            }
        )

    context.update(
        {
            "compare_enabled": True,
            "compare_fields": compare_fields,
            "compare_rows": compare_rows,
            "compare_summary": summary,
            "compare_left_snapshot": left_snapshot,
            "compare_right_snapshot": right_snapshot,
        }
    )
    return context


@login_required
def mega_projects(request):
    projects = [
        {
            "key": "mutolaa",
            "name": "Mutolaa",
            "icon": "bi-book",
            "accent": "var(--mega-blue)",
            "status": "API ulanmagan",
            "updated": "-",
            "logo_static": "img/mutolaa_logo.png",
        },
        {
            "key": "ustoz-ai",
            "name": "Ustoz AI",
            "icon": "bi-robot",
            "accent": "var(--mega-green)",
            "status": "API ulanmagan",
            "updated": "-",
            "logo": "https://ustoz.ai/icons/logo-ustozai.svg",
        },
        {
            "key": "uzchess",
            "name": "UzChess",
            "icon": "bi-diagram-3",
            "accent": "var(--mega-orange)",
            "status": "API ulanmagan",
            "updated": "-",
        },
        {
            "key": "qizlar-akademiyasi",
            "name": "Qizlar akademiyasi",
            "icon": "bi-gender-female",
            "accent": "var(--mega-pink)",
            "status": "API ulanmagan",
            "updated": "-",
        },
    ]
    return render(request, "mega_loyihalar/mega_projects.html", {"projects": projects})


def _render_mega_stats_page(
    request,
    *,
    snapshot_model,
    table_builder,
    compare_fields,
    page_title,
    refresh_url_name,
    column_labels,
):
    context = _build_mega_view_context(request, snapshot_model, table_builder, compare_fields)
    context.update(
        {
            "mega_title": page_title,
            "mega_refresh_url_name": refresh_url_name,
            "mega_column_labels": column_labels,
        }
    )
    return render(request, "mega_loyihalar/stats_common.html", context)


@login_required
def mega_mutolaa(request):
    return _render_mega_stats_page(
        request,
        snapshot_model=MutolaaStatSnapshot,
        table_builder=build_table,
        compare_fields=[
            ("users_total", "Foydalanuvchilar"),
            ("reading_books", "O'qilayotgan kitoblar"),
        ],
        page_title="Mutolaa",
        refresh_url_name="mega_mutolaa_refresh",
        column_labels={
            "mahalla_name": "Mahalla",
            "total_youth": "Jami yoshlar",
            "users_total": "Foydalanuvchilar",
            "users_ratio_percent": "Foydalanuvchi / yoshlar (%)",
            "reading_books": "O'qilayotgan kitoblar",
        },
    )


@login_required
def mega_ustoz_ai(request):
    return _render_mega_stats_page(
        request,
        snapshot_model=UstozAiStatSnapshot,
        table_builder=build_ustoz_table,
        compare_fields=[
            ("users_total", "Foydalanuvchilar"),
            ("video_views", "Video ko'rishlar"),
            ("certificates_count", "Olingan sertifikatlar"),
        ],
        page_title="Ustoz AI",
        refresh_url_name="mega_ustoz_ai_refresh",
        column_labels={
            "mahalla_name": "Mahalla",
            "total_youth": "Jami yoshlar",
            "users_total": "Foydalanuvchilar",
            "users_ratio_percent": "Foydalanuvchi / yoshlar (%)",
            "video_views": "Video ko'rishlar",
            "certificates_count": "Olingan sertifikatlar",
        },
    )


@login_required
@require_POST
def mega_ustoz_ai_refresh(request):
    snapshot, error = fetch_and_store_ustoz_ai_snapshot()
    if error:
        messages.error(request, f"Ustoz AI statistikasi yangilanmadi: {error}")
    else:
        messages.success(request, "Ustoz AI statistikasi yangilandi.")
    return redirect("mega_ustoz_ai")


@login_required
def mega_uzchess(request):
    return _render_mega_stats_page(
        request,
        snapshot_model=UzchessStatSnapshot,
        table_builder=build_uzchess_table,
        compare_fields=[
            ("users_total", "Profiles"),
            ("submissions_count", "Yechilgan boshqotirmalar"),
            ("games_count", "O'ynalgan o'yinlar"),
            ("certificates_count", "Olingan sertifikatlar"),
        ],
        page_title="UzChess",
        refresh_url_name="mega_uzchess_refresh",
        column_labels={
            "mahalla_name": "Mahalla",
            "total_youth": "Jami yoshlar",
            "users_total": "Profiles",
            "users_ratio_percent": "Ishtirokchi / yoshlar (%)",
            "submissions_count": "Yechilgan boshqotirmalar",
            "games_count": "O'ynalgan o'yinlar",
            "certificates_count": "Olingan sertifikatlar",
        },
    )


@login_required
@require_POST
def mega_uzchess_refresh(request):
    snapshot, error = fetch_and_store_uzchess_snapshot()
    if error:
        messages.error(request, f"UzChess statistikasi yangilanmadi: {error}")
    else:
        messages.success(request, "UzChess statistikasi yangilandi.")
    return redirect("mega_uzchess")


@login_required
def mega_girls_academy(request):
    return _render_mega_stats_page(
        request,
        snapshot_model=QizlarAkademiyasiStatSnapshot,
        table_builder=build_qizlar_table,
        compare_fields=[
            ("users_total", "Profiles"),
            ("submissions_count", "Yechilgan boshqotirmalar"),
            ("games_count", "O'ynalgan o'yinlar"),
            ("certificates_count", "Olingan sertifikatlar"),
        ],
        page_title="Qizlar akademiyasi",
        refresh_url_name="mega_girls_academy_refresh",
        column_labels={
            "mahalla_name": "Mahalla",
            "total_youth": "Jami yoshlar",
            "users_total": "Profiles",
            "users_ratio_percent": "Ishtirokchi / yoshlar (%)",
            "submissions_count": "Yechilgan boshqotirmalar",
            "games_count": "O'ynalgan o'yinlar",
            "certificates_count": "Olingan sertifikatlar",
        },
    )


@login_required
@require_POST
def mega_girls_academy_refresh(request):
    if not is_management_user(request.user):
        messages.error(request, "Yangilash faqat adminlar uchun ruxsat etilgan.")
        return redirect("mega_girls_academy")
    snapshot, error = fetch_and_store_qizlar_snapshot()
    if error:
        messages.error(request, f"Qizlar akademiyasi statistikasi yangilanmadi: {error}")
    else:
        messages.success(request, "Qizlar akademiyasi statistikasi yangilandi.")
    return redirect("mega_girls_academy")


@login_required
@require_POST
def mega_mutolaa_refresh(request):
    snapshot, error = fetch_and_store_mutolaa_snapshot()
    if error:
        messages.error(request, f"Mutolaa statistikasi yangilanmadi: {error}")
    else:
        messages.success(request, "Mutolaa statistikasi yangilandi.")
    return redirect("mega_mutolaa")
