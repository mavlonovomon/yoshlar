import gzip
import json
import logging
import re
from urllib.request import Request, urlopen

from django.conf import settings

from .models import (
    UstozAiStatSnapshot,
    UstozAiMahallaStat,
    UstozAiMahallaAlias,
    Mahalla,
)
from .stats_adapters import BaseStatsAdapter, pick_metric

logger = logging.getLogger(__name__)


DEFAULT_USTOZ_AI_URL = (
    "https://api.ustozaibot.uz/api/v1/statistics/village-school"
    "?district=Xazorasp+tumani&region=Xorazm+viloyati"
)


def get_ustoz_ai_url():
    return getattr(settings, "USTOZ_AI_STATS_URL", DEFAULT_USTOZ_AI_URL)


def _read_response(resp) -> str:
    raw = resp.read()
    encoding = (resp.headers.get("Content-Encoding") or "").lower()
    if "gzip" in encoding:
        raw = gzip.decompress(raw)
    charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace").lstrip("\ufeff")


def _fetch_json(url: str) -> dict:
    req = Request(
        url,
        headers={
            "User-Agent": "YoshlarTizimi/1.0",
            "Accept": "application/json",
        },
    )
    with urlopen(req, timeout=20) as resp:
        raw = _read_response(resp)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Ustoz AI JSON parse failed. Raw head: %s", raw[:200])
            raise


def _extract_items(payload: dict) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        # API structure: { data: { villages: [...] , schools: [...] } }
        data = payload.get("data")
        if isinstance(data, dict):
            villages = data.get("villages")
            if isinstance(villages, list):
                return villages
        for key in ("results", "data", "items"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
    return []


def _resolve_area_name(item: dict) -> str:
    for key in ("neighborhood", "name", "title", "mahalla", "village", "parent_name", "parent", "school", "school_name"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested_name = value.get("name") or value.get("title")
            if nested_name:
                return nested_name
    return "Noma'lum"


def _normalize_name(value: str) -> str:
    cleaned = value.lower()
    cleaned = cleaned.replace("mahalla", "")
    cleaned = re.sub(r"\bm\.?f\.?y\b", "", cleaned)
    cleaned = re.sub(r"\bmf\b", "", cleaned)
    cleaned = cleaned.replace("ʻ", "")
    cleaned = cleaned.replace("ʼ", "")
    cleaned = cleaned.replace("’", "")
    cleaned = cleaned.replace("‘", "")
    cleaned = cleaned.replace("`", "")
    cleaned = cleaned.replace("'", "")
    cleaned = cleaned.replace("oʻ", "o")
    cleaned = cleaned.replace("gʻ", "g")
    cleaned = re.sub(r"[^a-z0-9]+", "", cleaned)
    return cleaned.strip()


def _resolve_alias(api_name: str) -> UstozAiMahallaAlias:
    api_norm = _normalize_name(api_name)
    return BaseStatsAdapter.resolve_alias_record(
        UstozAiMahallaAlias,
        api_name=api_name,
        api_norm=api_norm,
    )


def _resolve_area_id(item: dict) -> str | None:
    for key in ("id", "pk", "uuid", "code"):
        value = item.get(key)
        if value is not None:
            return str(value)
    parent = item.get("parent")
    if isinstance(parent, dict) and parent.get("id"):
        return str(parent.get("id"))
    return None


def _extract_metrics(item: dict) -> dict:
    metrics = {}
    for key, value in item.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            if key in ("id", "pk", "uuid", "code", "name", "title", "mahalla", "parent", "parent_name", "school"):
                continue
            metrics[key] = value
    return metrics


class UstozAiStatsAdapter(BaseStatsAdapter):
    snapshot_model = UstozAiStatSnapshot
    stat_model = UstozAiMahallaStat
    unknown_error_message = "Noma'lum xatolik (logni tekshiring)"
    log_unknown_error = True
    logger = logger

    def get_url(self):
        return get_ustoz_ai_url()

    def fetch_payload(self, url):
        return _fetch_json(url)

    def iter_items(self, payload):
        return _extract_items(payload)

    def resolve_alias(self, area_name):
        return _resolve_alias(area_name)

    def resolve_area_name(self, item):
        return _resolve_area_name(item)

    def resolve_external_id(self, item):
        return _resolve_area_id(item)

    def extract_metrics(self, item):
        return _extract_metrics(item)

    def build_stat_instance(self, snapshot, alias, item, area_name, area_external_id, metrics):
        return UstozAiMahallaStat(
            snapshot=snapshot,
            mahalla=alias.mahalla,
            area_external_id=area_external_id,
            area_name=area_name,
            metrics=metrics,
        )


_adapter = UstozAiStatsAdapter()


def save_ustoz_ai_snapshot(payload: dict, source_url: str | None = None) -> UstozAiStatSnapshot:
    return _adapter.build_snapshot(payload, source_url or get_ustoz_ai_url())


def fetch_and_store_ustoz_ai_snapshot() -> tuple[UstozAiStatSnapshot | None, str | None]:
    return _adapter.fetch_and_store()


def build_table(
    snapshot: UstozAiStatSnapshot | None,
    mahallas: list[Mahalla] | None = None,
    youth_counts: dict[int, int] | None = None,
) -> tuple[list[str], list[dict], dict | None]:
    if not snapshot:
        return [], [], None

    rows = list(snapshot.area_stats.select_related("mahalla").all())
    row_by_mahalla_id = {row.mahalla_id: row for row in rows if row.mahalla_id}

    if mahallas is None:
        mahallas = list({row.mahalla for row in rows if row.mahalla})

    youth_counts = youth_counts or {}

    ordered_columns = [
        "mahalla_name",
        "total_youth",
        "users_total",
        "users_ratio_percent",
        "video_views",
        "certificates_count",
    ]
    table_rows = []
    total_youth_sum = 0
    total_users_sum = 0
    total_views_sum = 0
    total_cert_sum = 0
    for mahalla in mahallas:
        row = row_by_mahalla_id.get(mahalla.id)
        metrics = row.metrics if row else {}
        item = {"mahalla_name": mahalla.name}
        item["row_class"] = "row-missing" if row is None else ""

        total_youth = youth_counts.get(mahalla.id)
        users_total = pick_metric(
            metrics,
            ["users_total", "user_count", "users", "student_count", "students_count", "active_users"],
        )
        video_views = pick_metric(metrics, ["views"])
        certificates_count = pick_metric(metrics, ["certificates"])

        item["total_youth"] = total_youth if total_youth is not None else 0
        item["users_total"] = users_total if users_total is not None else 0
        ratio_value = None
        if total_youth and users_total is not None:
            try:
                ratio_value = (float(users_total) / float(total_youth)) * 100
                item["users_ratio_percent"] = f"{ratio_value:.1f}%"
            except Exception:
                item["users_ratio_percent"] = "—"
        else:
            item["users_ratio_percent"] = "—"
        item["video_views"] = video_views if video_views is not None else 0
        item["certificates_count"] = certificates_count if certificates_count is not None else 0
        item["ratio_value"] = ratio_value
        if ratio_value is None:
            item["ratio_class"] = ""
        elif ratio_value >= 90:
            item["ratio_class"] = "ratio-good"
        elif ratio_value >= 50:
            item["ratio_class"] = "ratio-mid"
        else:
            item["ratio_class"] = "ratio-low"

        total_youth_sum += item["total_youth"] or 0
        total_users_sum += item["users_total"] or 0
        total_views_sum += item["video_views"] or 0
        total_cert_sum += item["certificates_count"] or 0
        table_rows.append(item)

    # sort desc by ratio (None last)
    def _sort_key(row):
        value = row["ratio_value"] if row["ratio_value"] is not None else 0
        return (row["ratio_value"] is None, -value)

    table_rows.sort(key=_sort_key)

    total_row = {
        "mahalla_name": "Tuman bo'yicha jami",
        "total_youth": total_youth_sum,
        "users_total": total_users_sum,
        "video_views": total_views_sum,
        "certificates_count": total_cert_sum,
        "ratio_value": None,
    }
    if total_youth_sum:
        total_row["users_ratio_percent"] = f"{(total_users_sum / total_youth_sum) * 100:.1f}%"
    else:
        total_row["users_ratio_percent"] = "—"

    return ordered_columns, table_rows, total_row
