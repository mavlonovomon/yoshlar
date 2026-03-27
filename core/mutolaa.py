import json
import re
from urllib.request import Request, urlopen

from django.conf import settings

from .models import MutolaaStatSnapshot, MutolaaMahallaStat, MutolaaMahallaAlias, Mahalla
from .stats_adapters import BaseStatsAdapter, pick_metric


DEFAULT_MUTOLAA_URL = (
    "https://api.mutolaa.com/api/v1/stats/NeighborhoodForStatistics/"
    "?offset=0&limit=47&parent__parent=8649&ordering&parent=8857"
)


def get_mutolaa_url():
    return getattr(settings, "MUTOLAA_STATS_URL", DEFAULT_MUTOLAA_URL)


def _fetch_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "YoshlarTizimi/1.0"})
    with urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw)


def _extract_items(payload: dict) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("results", "data", "items"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
    return []


def _resolve_mahalla_name(item: dict) -> str:
    for key in ("name", "title", "mahalla", "parent_name", "parent"):
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


def _resolve_alias(api_name: str) -> MutolaaMahallaAlias:
    api_norm = _normalize_name(api_name)
    return BaseStatsAdapter.resolve_alias_record(
        MutolaaMahallaAlias,
        api_name=api_name,
        api_norm=api_norm,
    )


def _resolve_mahalla_id(item: dict) -> str | None:
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
            if key in ("id", "pk", "uuid", "code", "name", "title", "mahalla", "parent", "parent_name"):
                continue
            metrics[key] = value
    return metrics


class MutolaaStatsAdapter(BaseStatsAdapter):
    snapshot_model = MutolaaStatSnapshot
    stat_model = MutolaaMahallaStat

    def get_url(self):
        return get_mutolaa_url()

    def fetch_payload(self, url):
        return _fetch_json(url)

    def iter_items(self, payload):
        return _extract_items(payload)

    def resolve_alias(self, area_name):
        return _resolve_alias(area_name)

    def resolve_area_name(self, item):
        return _resolve_mahalla_name(item)

    def resolve_external_id(self, item):
        return _resolve_mahalla_id(item)

    def extract_metrics(self, item):
        return _extract_metrics(item)

    def build_stat_instance(self, snapshot, alias, item, area_name, area_external_id, metrics):
        return MutolaaMahallaStat(
            snapshot=snapshot,
            mahalla=alias.mahalla,
            mahalla_external_id=area_external_id,
            mahalla_name=area_name,
            metrics=metrics,
        )


_adapter = MutolaaStatsAdapter()


def save_mutolaa_snapshot(payload: dict, source_url: str | None = None) -> MutolaaStatSnapshot:
    return _adapter.build_snapshot(payload, source_url or get_mutolaa_url())


def fetch_and_store_mutolaa_snapshot() -> tuple[MutolaaStatSnapshot | None, str | None]:
    return _adapter.fetch_and_store()


def build_table(
    snapshot: MutolaaStatSnapshot | None,
    mahallas: list[Mahalla] | None = None,
    youth_counts: dict[int, int] | None = None,
) -> tuple[list[str], list[dict], dict | None]:
    if not snapshot:
        return [], [], None

    rows = list(snapshot.mahalla_stats.select_related("mahalla").all())
    row_by_mahalla_id = {row.mahalla_id: row for row in rows if row.mahalla_id}

    if mahallas is None:
        mahallas = list({row.mahalla for row in rows if row.mahalla})

    youth_counts = youth_counts or {}

    ordered_columns = [
        "mahalla_name",
        "total_youth",
        "users_total",
        "users_ratio_percent",
        "reading_books",
    ]
    table_rows = []
    total_youth_sum = 0
    total_users_sum = 0
    total_books_sum = 0
    for mahalla in mahallas:
        row = row_by_mahalla_id.get(mahalla.id)
        metrics = row.metrics if row else {}
        item = {"mahalla_name": mahalla.name}
        item["row_class"] = "row-missing" if row is None else ""

        total_youth = youth_counts.get(mahalla.id)
        users_total = pick_metric(metrics, ["users_total", "user_count", "users", "foydalanuvchilar"])
        reading_books = pick_metric(metrics, ["read_book_count"])

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
        item["reading_books"] = reading_books if reading_books is not None else 0
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
        total_books_sum += item["reading_books"] or 0
        table_rows.append(item)

    # sort descending by ratio (None goes last)
    def _sort_key(row):
        value = row["ratio_value"] if row["ratio_value"] is not None else 0
        return (row["ratio_value"] is None, -value)

    table_rows.sort(key=_sort_key)

    total_row = {
        "mahalla_name": "Tuman bo'yicha jami",
        "total_youth": total_youth_sum,
        "users_total": total_users_sum,
        "reading_books": total_books_sum,
        "ratio_value": None,
    }
    if total_youth_sum:
        total_row["users_ratio_percent"] = f"{(total_users_sum / total_youth_sum) * 100:.1f}%"
    else:
        total_row["users_ratio_percent"] = "—"

    return ordered_columns, table_rows, total_row
