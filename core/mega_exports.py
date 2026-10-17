import io
import math
import re

from django.http import HttpResponse, HttpResponseBadRequest
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .ibrat import build_table as build_ibrat_table
from .models import (
    IbratFarzandlariStatSnapshot,
    MutolaaStatSnapshot,
    QizlarAkademiyasiStatSnapshot,
    UstozAiStatSnapshot,
    UzchessStatSnapshot,
)
from .mutolaa import build_table as build_mutolaa_table
from .qizlar_akademiyasi import build_table as build_qizlar_table
from .ustoz_ai import build_table as build_ustoz_table
from .uzchess import build_table as build_uzchess_table


MEGA_EXPORTS = {
    "mutolaa": {
        "title": "Mutolaa",
        "snapshot_model": MutolaaStatSnapshot,
        "table_builder": build_mutolaa_table,
        "column_labels": {
            "mahalla_name": "Mahalla",
            "total_youth": "14-30 yoshlar",
            "users_total": "Foydalanuvchilar",
            "users_ratio_percent": "Foydalanuvchi / yoshlar (%)",
            "reading_books": "O'qilayotgan kitoblar",
        },
        "age_min": 14,
        "age_max": 30,
    },
    "ustoz-ai": {
        "title": "Ustoz AI",
        "snapshot_model": UstozAiStatSnapshot,
        "table_builder": build_ustoz_table,
        "column_labels": {
            "mahalla_name": "Mahalla",
            "total_youth": "14-30 yoshlar",
            "users_total": "Foydalanuvchilar",
            "users_ratio_percent": "Foydalanuvchi / yoshlar (%)",
            "video_views": "Video ko'rishlar",
            "certificates_count": "Olingan sertifikatlar",
        },
        "age_min": 14,
        "age_max": 30,
    },
    "uzchess": {
        "title": "UzChess",
        "snapshot_model": UzchessStatSnapshot,
        "table_builder": build_uzchess_table,
        "column_labels": {
            "mahalla_name": "Mahalla",
            "total_youth": "14-30 yoshlar",
            "users_total": "Profiles",
            "users_ratio_percent": "Ishtirokchi / yoshlar (%)",
            "submissions_count": "Yechilgan boshqotirmalar",
            "games_count": "O'ynalgan o'yinlar",
            "certificates_count": "Olingan sertifikatlar",
        },
        "age_min": 14,
        "age_max": 30,
    },
    "qizlar-akademiyasi": {
        "title": "Qizlar akademiyasi",
        "snapshot_model": QizlarAkademiyasiStatSnapshot,
        "table_builder": build_qizlar_table,
        "column_labels": {
            "mahalla_name": "Mahalla",
            "total_youth": "14+ ayol-qizlar",
            "users_total": "Profiles",
            "users_ratio_percent": "Ishtirokchi / 14+ ayol-qizlar (%)",
            "submissions_count": "Yechilgan boshqotirmalar",
            "games_count": "O'ynalgan o'yinlar",
            "certificates_count": "Olingan sertifikatlar",
        },
        "gender_filter": "Женский",
        "age_min": 14,
        "age_max": 30,
    },
    "ibrat-farzandlari": {
        "title": "Ibrat Farzandlari",
        "snapshot_model": IbratFarzandlariStatSnapshot,
        "table_builder": build_ibrat_table,
        "column_labels": {
            "mahalla_name": "Mahalla",
            "total_youth": "14-30 yoshlar",
            "users_total": "Foydalanuvchilar",
            "users_ratio_percent": "Foydalanuvchi / yoshlar (%)",
            "certificates_count": "Olingan sertifikatlar",
        },
        "age_min": 14,
        "age_max": 30,
    },
}

_COLUMN_LABELS = {
    "total_youth": "Yoshlar soni",
    "users_total": "Ishtirokchilar",
    "users_ratio_percent": "Ishtirokchilar / yoshlar (%)",
    "reading_books": "O'qilayotgan kitoblar",
    "video_views": "Video ko'rishlar",
    "certificates_count": "Sertifikatlar",
    "submissions_count": "Yechilgan boshqotirmalar",
    "games_count": "O'ynalgan o'yinlar",
}
_HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")
_TOTAL_FILL = PatternFill("solid", fgColor="D9E2F3")
_THIN_BORDER = Border(
    left=Side(style="thin", color="B0B8C4"),
    right=Side(style="thin", color="B0B8C4"),
    top=Side(style="thin", color="B0B8C4"),
    bottom=Side(style="thin", color="B0B8C4"),
)


def _to_number(value):
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, str):
        text = value.strip()
        if not text or text in {"-", "—", "–"}:
            return None
        if not re.fullmatch(r"[-+]?\d[\d\s,]*(?:\.\d+)?%?", text):
            return None
        normalized = re.sub(r"[\s,%]", "", text)
        try:
            number = float(normalized)
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None


def _parse_options(post, available_ids):
    selected_ids = list(dict.fromkeys(post.getlist("snapshot_ids")))
    if not selected_ids:
        raise ValueError("Excel fayli uchun kamida bitta snapshotni tanlang.")
    if any(snapshot_id not in available_ids for snapshot_id in selected_ids):
        raise ValueError("Tanlangan snapshotlardan biri topilmadi. Sahifani yangilab, qayta urinib ko'ring.")

    compare_latest = post.get("compare_latest") == "on"
    compare_first_last = post.get("compare_first_last") == "on"
    if (compare_latest or compare_first_last) and len(selected_ids) < 2:
        raise ValueError("Farq ustunlarini qo'shish uchun kamida ikkita snapshotni tanlang.")

    color_mode = post.get("color_mode", "traffic")
    if color_mode not in {"traffic", "relative", "custom"}:
        raise ValueError("Ranglash usuli noto'g'ri tanlangan.")

    try:
        red_limit = float(post.get("red_limit", "50"))
        yellow_limit = float(post.get("yellow_limit", "80"))
    except (TypeError, ValueError):
        raise ValueError("Qizil va sariq rang chegaralariga 0 dan 100 gacha son kiriting.") from None

    if not (math.isfinite(red_limit) and math.isfinite(yellow_limit)):
        raise ValueError("Rang chegaralari chekli son bo'lishi kerak.")
    if not (0 <= red_limit < yellow_limit <= 100):
        raise ValueError("Qizil chegara sariq chegaradan kichik, ikkalasi ham 0-100 oralig'ida bo'lishi kerak.")

    extra_columns = post.getlist("extra_columns")

    return {
        "snapshot_ids": selected_ids,
        "compare_latest": compare_latest,
        "compare_first_last": compare_first_last,
        "color_mode": color_mode,
        "red_limit": red_limit,
        "yellow_limit": yellow_limit,
        "extra_columns": extra_columns,
    }


def _blend_color(start, end, ratio):
    start_rgb = tuple(int(start[index:index + 2], 16) for index in (0, 2, 4))
    end_rgb = tuple(int(end[index:index + 2], 16) for index in (0, 2, 4))
    rgb = tuple(round(a + (b - a) * ratio) for a, b in zip(start_rgb, end_rgb))
    return "".join(f"{channel:02X}" for channel in rgb)


def _traffic_color(value):
    value = min(100, max(0, value))
    if value <= 50:
        return _blend_color("F8696B", "FFEB84", value / 50)
    return _blend_color("FFEB84", "63BE7B", (value - 50) / 50)


def _relative_color(value, minimum, maximum):
    if maximum <= minimum:
        return "63BE7B"
    position = (value - minimum) / (maximum - minimum)
    if position <= 0.5:
        return _blend_color("F8696B", "FFEB84", position * 2)
    return _blend_color("FFEB84", "63BE7B", (position - 0.5) * 2)


def _row_color(value, options, relative_bounds):
    if value is None:
        return None
    if options["color_mode"] == "traffic":
        return _traffic_color(value)
    if options["color_mode"] == "relative":
        return _relative_color(value, *relative_bounds)
    if value <= options["red_limit"]:
        return "F8696B"
    if value <= options["yellow_limit"]:
        return "FFEB84"
    return "63BE7B"


def _excel_value(value):
    number = _to_number(value)
    if number is not None:
        return number
    return value if value is not None else None


def build_mega_excel_response(project_key, post, *, mahallas, youth_counts):
    config = MEGA_EXPORTS.get(project_key)
    if config is None:
        return HttpResponseBadRequest("Mega loyiha topilmadi.")

    available = list(
        config["snapshot_model"].objects.order_by("-snapshot_date", "-fetched_at")[:50]
    )
    available_by_id = {str(snapshot.pk): snapshot for snapshot in available}
    try:
        options = _parse_options(post, set(available_by_id))
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    if len(options["snapshot_ids"]) > 50:
        return HttpResponseBadRequest("Bir faylga ko'pi bilan 50 ta snapshot qo'shish mumkin.")

    snapshots = [
        available_by_id[snapshot_id]
        for snapshot_id in options["snapshot_ids"]
    ]
    snapshots.sort(key=lambda snapshot: (snapshot.snapshot_date, snapshot.fetched_at, snapshot.pk))

    columns_by_snapshot = []
    rows_by_snapshot = []
    totals_by_snapshot = []
    for snapshot in snapshots:
        columns, rows, total = config["table_builder"](
            snapshot,
            mahallas=mahallas,
            youth_counts=youth_counts,
        )
        columns_by_snapshot.append(columns)
        rows_by_snapshot.append({row["mahalla_name"]: row for row in rows})
        totals_by_snapshot.append(total or {})

    base_metric = "users_total"
    if base_metric not in columns_by_snapshot[-1]:
        candidates = [k for k in columns_by_snapshot[-1] if k not in {"mahalla_name", "total_youth"}]
        base_metric = candidates[0] if candidates else "users_total"

    available_extra = [
        key for key in columns_by_snapshot[-1]
        if key not in {"mahalla_name", "total_youth", base_metric}
    ]
    selected_extra = [
        key for key in options.get("extra_columns", [])
        if key in available_extra
    ]
    metric_keys = [base_metric] + selected_extra

    all_names = set()
    for rows in rows_by_snapshot:
        all_names.update(rows)

    latest_rows = rows_by_snapshot[-1]
    all_latest_percentages = [
        _to_number(row.get("users_ratio_percent"))
        for row in latest_rows.values()
    ]
    all_latest_percentages = [value for value in all_latest_percentages if value is not None]
    relative_bounds = (
        (min(all_latest_percentages), max(all_latest_percentages))
        if all_latest_percentages
        else (0, 0)
    )

    def sort_key(name):
        latest_percent = _to_number(latest_rows.get(name, {}).get("users_ratio_percent"))
        return (latest_percent is None, -(latest_percent or 0), str(name).casefold())

    ordered_names = sorted(all_names, key=sort_key)

    delta_pairs = []
    if options["compare_latest"]:
        delta_pairs.append(("So'nggi 2 snapshot farqi", len(snapshots) - 2, len(snapshots) - 1))
    if options["compare_first_last"]:
        delta_pairs.append(("Birinchi va oxirgi snapshot farqi", 0, len(snapshots) - 1))

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Mega loyiha"
    worksheet.sheet_view.showGridLines = False

    snapshot_heading = " | ".join(
        f"{config['title']} - {snapshot.fetched_at:%d.%m.%Y %H:%M}"
        for snapshot in snapshots
    )
    column_count = 2 + len(metric_keys) * (len(snapshots) + len(delta_pairs)) + 1
    worksheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=column_count)
    title_cell = worksheet.cell(row=1, column=1, value=f"{config['title']} — mahallalar statistikasi")
    title_cell.font = Font(bold=True, size=16, color="FFFFFF")
    title_cell.fill = _HEADER_FILL
    title_cell.alignment = Alignment(vertical="center")
    worksheet.row_dimensions[1].height = 28
    worksheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=column_count)
    subtitle = worksheet.cell(
        row=2,
        column=1,
        value=f"Snapshotlar: {snapshot_heading}. Rang va tartib so'nggi tanlangan snapshot foizi bo'yicha.",
    )
    subtitle.font = Font(italic=True, color="666666")

    worksheet.merge_cells(start_row=3, start_column=1, end_row=4, end_column=1)
    worksheet.cell(row=3, column=1, value="Mahalla")

    youth_col_label = config["column_labels"].get("total_youth", "14-30 yoshlar")
    worksheet.merge_cells(start_row=3, start_column=2, end_row=4, end_column=2)
    worksheet.cell(row=3, column=2, value=youth_col_label)

    current_column = 3
    snapshot_column_indexes = []
    for snapshot_index, snapshot in enumerate(snapshots):
        first_column = current_column
        snapshot_column_indexes.append({})
        for field_key in metric_keys:
            snapshot_column_indexes[-1][field_key] = current_column
            label = config["column_labels"].get(field_key, _COLUMN_LABELS.get(field_key, field_key.replace("_", " ").capitalize()))
            worksheet.cell(row=4, column=current_column, value=label)
            current_column += 1
        if first_column < current_column - 1:
            worksheet.merge_cells(
                start_row=3,
                start_column=first_column,
                end_row=3,
                end_column=current_column - 1,
            )
        worksheet.cell(
            row=3,
            column=first_column,
            value=f"{snapshot.fetched_at:%d.%m.%Y %H:%M}",
        )

    delta_column_indexes = []
    for label, _old_index, _new_index in delta_pairs:
        first_column = current_column
        delta_column_indexes.append({})
        for field_key in metric_keys:
            delta_column_indexes[-1][field_key] = current_column
            metric_label = config["column_labels"].get(field_key, _COLUMN_LABELS.get(field_key, field_key.replace("_", " ").capitalize()))
            diff_label = f"Farq: {metric_label}" if len(metric_keys) > 1 else f"Farq ({metric_label})"
            worksheet.cell(row=4, column=current_column, value=diff_label)
            current_column += 1
        if first_column < current_column - 1:
            worksheet.merge_cells(
                start_row=3,
                start_column=first_column,
                end_row=3,
                end_column=current_column - 1,
            )
        worksheet.cell(row=3, column=first_column, value=label)

    final_ratio_column = current_column
    worksheet.merge_cells(
        start_row=3,
        start_column=final_ratio_column,
        end_row=4,
        end_column=final_ratio_column,
    )
    worksheet.cell(row=3, column=final_ratio_column, value="Jami foiz")

    for row in worksheet.iter_rows(min_row=3, max_row=4, max_col=column_count):
        for cell in row:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = _HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = _THIN_BORDER
    worksheet.row_dimensions[3].height = 24
    worksheet.row_dimensions[4].height = 42

    data_start_row = 5
    for row_index, name in enumerate(ordered_names, start=data_start_row):
        worksheet.cell(row=row_index, column=1, value=name)
        total_youth_value = _excel_value(latest_rows.get(name, {}).get("total_youth"))
        cell_youth = worksheet.cell(row=row_index, column=2, value=total_youth_value)
        if total_youth_value is not None:
            cell_youth.number_format = '#,##0'

        for snapshot_index, rows in enumerate(rows_by_snapshot):
            source_row = rows.get(name, {})
            for field_key, column_index in snapshot_column_indexes[snapshot_index].items():
                value = _excel_value(source_row.get(field_key))
                cell = worksheet.cell(row=row_index, column=column_index, value=value)
                if field_key == "users_ratio_percent" and value is not None:
                    cell.number_format = '0.0"%"'
                elif value is not None:
                    cell.number_format = '#,##0'
        for delta_index, (_label, old_index, new_index) in enumerate(delta_pairs):
            old_row = rows_by_snapshot[old_index].get(name, {})
            new_row = rows_by_snapshot[new_index].get(name, {})
            for field_key, column_index in delta_column_indexes[delta_index].items():
                old_value = _to_number(old_row.get(field_key))
                new_value = _to_number(new_row.get(field_key))
                value = new_value - old_value if old_value is not None and new_value is not None else None
                cell = worksheet.cell(row=row_index, column=column_index, value=value)
                if field_key == "users_ratio_percent" and value is not None:
                    cell.number_format = '+0.0"%";[Red]-0.0"%"'
                elif value is not None:
                    cell.number_format = '+#,##0;[Red]-#,##0;0'

        latest_percent = _to_number(latest_rows.get(name, {}).get("users_ratio_percent"))
        final_ratio_cell = worksheet.cell(
            row=row_index,
            column=final_ratio_column,
            value=latest_percent,
        )
        if latest_percent is not None:
            final_ratio_cell.number_format = '0.0"%"'
        final_ratio_cell.font = Font(bold=True)

        for column_index in range(1, column_count + 1):
            cell = worksheet.cell(row=row_index, column=column_index)
            cell.border = _THIN_BORDER
            cell.alignment = Alignment(vertical="center", wrap_text=column_index == 1)
            if latest_percent is not None:
                value_for_fill = latest_percent
                if options["color_mode"] == "relative":
                    color = _row_color(value_for_fill, options, relative_bounds)
                else:
                    color = _row_color(value_for_fill, options, (0, 0))
                if color:
                    cell.fill = PatternFill("solid", fgColor=color)

    total_row_index = data_start_row + len(ordered_names)
    total_label = "Tuman bo'yicha jami"
    worksheet.cell(row=total_row_index, column=1, value=total_label)

    total_youth_sum = _excel_value(totals_by_snapshot[-1].get("total_youth"))
    cell_total_youth = worksheet.cell(row=total_row_index, column=2, value=total_youth_sum)
    if total_youth_sum is not None:
        cell_total_youth.number_format = '#,##0'

    for snapshot_index, total in enumerate(totals_by_snapshot):
        for field_key, column_index in snapshot_column_indexes[snapshot_index].items():
            value = _excel_value(total.get(field_key))
            cell = worksheet.cell(row=total_row_index, column=column_index, value=value)
            if field_key == "users_ratio_percent" and value is not None:
                cell.number_format = '0.0"%"'
            elif value is not None:
                cell.number_format = '#,##0'
    for delta_index, (_label, old_index, new_index) in enumerate(delta_pairs):
        old_total = totals_by_snapshot[old_index]
        new_total = totals_by_snapshot[new_index]
        for field_key, column_index in delta_column_indexes[delta_index].items():
            old_value = _to_number(old_total.get(field_key))
            new_value = _to_number(new_total.get(field_key))
            value = new_value - old_value if old_value is not None and new_value is not None else None
            cell = worksheet.cell(row=total_row_index, column=column_index, value=value)
            if field_key == "users_ratio_percent" and value is not None:
                cell.number_format = '+0.0"%";[Red]-0.0"%"'
            elif value is not None:
                cell.number_format = '+#,##0;[Red]-#,##0;0'
    total_ratio = _to_number(totals_by_snapshot[-1].get("users_ratio_percent"))
    total_ratio_cell = worksheet.cell(
        row=total_row_index,
        column=final_ratio_column,
        value=total_ratio,
    )
    if total_ratio is not None:
        total_ratio_cell.number_format = '0.0"%"'
    for cell in worksheet[total_row_index]:
        cell.font = Font(bold=True)
        cell.fill = _TOTAL_FILL
        cell.border = _THIN_BORDER
        cell.alignment = Alignment(vertical="center", wrap_text=True)

    for column_index in range(1, column_count + 1):
        letter = get_column_letter(column_index)
        worksheet.column_dimensions[letter].width = 18 if column_index > 1 else 30
    worksheet.freeze_panes = "C5"
    worksheet.auto_filter.ref = f"A4:{get_column_letter(column_count)}{total_row_index}"

    buffer = io.BytesIO()
    workbook.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{project_key}-statistika.xlsx"'
    return response


def mega_excel_export(request, project_key, *, mahallas, youth_counts):
    return build_mega_excel_response(
        project_key,
        request.POST,
        mahallas=mahallas,
        youth_counts=youth_counts,
    )
