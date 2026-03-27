import json
from urllib.request import Request, urlopen
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from django.conf import settings

from .models import (
    UzchessStatSnapshot,
    UzchessMahallaStat,
    UzchessMahallaAlias,
    Mahalla,
)
from .stats_adapters import BaseStatsAdapter


DEFAULT_UZCHESS_URL = (
    "https://api.uzchesss.uz/api/statistics/count-by-neighborhood"
    "?page=1&region=Xorazm+viloyati&district=Xazorasp+tumani"
)


def get_uzchess_url():
    return getattr(settings, "UZCHESS_STATS_URL", DEFAULT_UZCHESS_URL)


def _fetch_json(url: str) -> dict | list:
    req = Request(url, headers={"User-Agent": "YoshlarTizimi/1.0"})
    with urlopen(req, timeout=30) as resp:
        data = resp.read().decode("utf-8", errors="ignore")
        return json.loads(data)


def _with_page(url: str, page: int) -> str:
    """URL query ichidagi `page` parametrini yangilaydi (yoki qo'shadi)."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["page"] = str(page)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), parts.fragment))


def _get_start_page(url: str) -> int:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    try:
        return int(query.get("page") or 1)
    except Exception:
        return 1


def _alias_key(api_name: str) -> str:
    # Hech narsani "tozalamasdan" admin panelda API nomi qanday kelsa shunday saqlaymiz.
    # Faqat bosh/oxiridagi whitespace olib tashlanadi.
    return (api_name or "").strip()


def _resolve_alias(api_name: str) -> UzchessMahallaAlias:
    api_key = _alias_key(api_name)
    return BaseStatsAdapter.resolve_alias_record(
        UzchessMahallaAlias,
        api_name=api_key,
        api_norm=api_key,
    )


def _extract_items(payload: dict | list) -> list[dict]:
    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return []

    for key in ("results", "data", "items", "list", "neighborhoods", "stats", "statistics"):
        value = payload.get(key)
        if isinstance(value, list):
            return value

    for value in payload.values():
        if isinstance(value, dict):
            for key in ("results", "data", "items", "list", "neighborhoods", "stats", "statistics"):
                nested = value.get(key)
                if isinstance(nested, list):
                    return nested

    return []


def _resolve_area_name(item: dict) -> str:
    # UzChess endpointida mahalla nomi odatda `_id` ichida keladi.
    for key in ("_id", "mahalla", "neighborhood", "village", "name"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Noma'lum"


def _extract_metrics(item: dict, area_key: str | None) -> dict:
    metrics = {}
    for key, value in item.items():
        if key == area_key:
            continue
        metrics[key] = value
    return metrics


class UzchessStatsAdapter(BaseStatsAdapter):
    snapshot_model = UzchessStatSnapshot
    stat_model = UzchessMahallaStat
    unknown_error_message = "JSON o'qib bo'lmadi"

    def get_url(self):
        return get_uzchess_url()

    def fetch_payload(self, url):
        all_items: list[dict] = []
        raw_pages: list[dict | list] = []

        start_page = _get_start_page(url)
        page = start_page

        for _ in range(1, 51):
            page_url = _with_page(url, page)
            raw = _fetch_json(page_url)
            raw_pages.append(raw)

            items = _extract_items(raw)
            if not items:
                break
            all_items.extend([i for i in items if isinstance(i, dict)])
            page += 1

        return {"items": all_items, "raw_pages": raw_pages}

    def iter_items(self, payload):
        return payload.get("items", [])

    def resolve_alias(self, area_name):
        return _resolve_alias(area_name)

    def resolve_area_name(self, item):
        return _resolve_area_name(item)

    def resolve_external_id(self, item):
        return str(item.get("id") or "") or None

    def extract_metrics(self, item):
        area_key = "_id" if "_id" in item else None
        return _extract_metrics(item, area_key)

    def build_stat_instance(self, snapshot, alias, item, area_name, area_external_id, metrics):
        return UzchessMahallaStat(
            snapshot=snapshot,
            mahalla=alias.mahalla,
            area_external_id=area_external_id,
            area_name=area_name,
            metrics=metrics,
        )


_adapter = UzchessStatsAdapter()


def save_uzchess_snapshot(payload: dict, source_url: str | None = None) -> UzchessStatSnapshot:
    return _adapter.build_snapshot(payload, source_url or get_uzchess_url())


def fetch_and_store_uzchess_snapshot() -> tuple[UzchessStatSnapshot | None, str | None]:
    return _adapter.fetch_and_store()


def build_table(
    snapshot: UzchessStatSnapshot | None,
    mahallas: list[Mahalla] | None = None,
    youth_counts: dict[int, int] | None = None,
) -> tuple[list[str], list[dict], dict | None]:
    if not snapshot:
        return [], [], None

    rows = list(snapshot.area_stats.select_related("mahalla").all())

    # Alias key larni keyinroq admin o'zgartirgan bo'lsa ham (snapshot qayta olinmasdan)
    # jadvalda ko'rinishi uchun, mahalla_id bo'lmagan satrlarni ham alias orqali ulab ko'ramiz.
    alias_to_mahalla_id = {
        a.api_name: a.mahalla_id
        for a in UzchessMahallaAlias.objects.exclude(mahalla_id__isnull=True)
    }
    row_by_mahalla_id: dict[int, UzchessMahallaStat] = {}
    for row in rows:
        mahalla_id = row.mahalla_id
        if not mahalla_id:
            mahalla_id = alias_to_mahalla_id.get((row.area_name or "").strip())
        if mahalla_id:
            row_by_mahalla_id[mahalla_id] = row

    if mahallas is None:
        mahallas = list({row.mahalla for row in rows if row.mahalla})

    youth_counts = youth_counts or {}

    ordered_columns = [
        "mahalla_name",
        "total_youth",
        "users_total",
        "users_ratio_percent",
        "submissions_count",
        "games_count",
        "certificates_count",
    ]

    table_rows = []
    total_youth_sum = 0
    total_users_sum = 0
    total_submissions_sum = 0
    total_games_sum = 0
    total_certificates_sum = 0

    for mahalla in mahallas:
        row = row_by_mahalla_id.get(mahalla.id)
        metrics = row.metrics if row else {}

        total_youth = youth_counts.get(mahalla.id) or 0
        profiles = metrics.get("profiles") or 0
        submissions = metrics.get("submissions") or 0
        games_count = metrics.get("games_count") or 0
        certificates = metrics.get("certificates") or 0

        ratio_value = None
        if total_youth and profiles is not None:
            try:
                ratio_value = (float(profiles) / float(total_youth)) * 100
                ratio_text = f"{ratio_value:.1f}%"
            except Exception:
                ratio_text = "—"
        else:
            ratio_text = "—"

        if ratio_value is None:
            ratio_class = ""
        elif ratio_value >= 90:
            ratio_class = "ratio-good"
        elif ratio_value >= 50:
            ratio_class = "ratio-mid"
        else:
            ratio_class = "ratio-low"

        item = {
            "mahalla_name": mahalla.name,
            "row_class": "row-missing" if row is None else "",
            "total_youth": total_youth,
            "users_total": profiles,
            "users_ratio_percent": ratio_text,
            "submissions_count": submissions,
            "games_count": games_count,
            "certificates_count": certificates,
            "ratio_value": ratio_value,
            "ratio_class": ratio_class,
        }
        table_rows.append(item)

        total_youth_sum += total_youth
        total_users_sum += profiles
        total_submissions_sum += submissions
        total_games_sum += games_count
        total_certificates_sum += certificates

    # sort desc by ratio (None last)
    def _sort_key(row):
        value = row["ratio_value"] if row["ratio_value"] is not None else 0
        return (row["ratio_value"] is None, -value)

    table_rows.sort(key=_sort_key)

    total_row = {
        "mahalla_name": "Tuman bo'yicha jami",
        "total_youth": total_youth_sum,
        "users_total": total_users_sum,
        "submissions_count": total_submissions_sum,
        "games_count": total_games_sum,
        "certificates_count": total_certificates_sum,
        "ratio_value": None,
    }
    if total_youth_sum:
        total_row["users_ratio_percent"] = f"{(total_users_sum / total_youth_sum) * 100:.1f}%"
    else:
        total_row["users_ratio_percent"] = "—"

    return ordered_columns, table_rows, total_row
