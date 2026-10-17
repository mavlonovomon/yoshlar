import logging
import re
import socket
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from django.conf import settings

from .models import (
    IbratFarzandlariStatSnapshot,
    IbratFarzandlariMahallaStat,
    IbratFarzandlariMahallaAlias,
    Mahalla,
)
from .stats_adapters import BaseStatsAdapter, pick_metric

logger = logging.getLogger(__name__)

DEFAULT_IBRAT_URL = (
    "https://api.ibrat.dev/v1/statistics/by-locality/public"
    "?region_id=16&district_id=1733220&page=1&limit=100"
)

# Core Mahalla nomlari bilan API nomlarining dastlabki xaritasi
INITIAL_ALIAS_MAPPING = {
    "g.g'ulom mahallasi": "Gʻ.Gʻofur",
    "g'g'ulom mahallasi": "Gʻ.Gʻofur",
    "g g'ulom mahallasi": "Gʻ.Gʻofur",
    "ataliq mahallasi": "Otaliq",
    "otaliq": "Otaliq",
    "juvarxoz mahallasi": "Juvarxos",
    "juvarxos": "Juvarxos",
    "sulaymon qalʻʻasi": "Sulaymon qalʻasi",
    "sulaymon qalʻasi": "Sulaymon qalʻasi",
    "paxlovon maxmud maxallasi": "Paxlavon Maxmud",
    "paxlavon maxmud": "Paxlavon Maxmud",
    "j.manguberdi maxallasi": "Jaloladdin Manguberdi",
    "jaloladdin manguberdi": "Jaloladdin Manguberdi",
}


def get_ibrat_url():
    return getattr(settings, "IBRAT_STATS_URL", DEFAULT_IBRAT_URL)


_session = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        try:
            import urllib3.util.connection
            urllib3.util.connection.allowed_gai_family = lambda: socket.AF_INET
        except Exception:
            pass

        _session = requests.Session()
        _session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "uz,ru,en;q=0.9",
        })
    return _session


def _fetch_json(url: str, session: requests.Session | None = None) -> dict:
    s = session or _get_session()
    resp = s.get(url, timeout=(5, 20))
    resp.raise_for_status()
    try:
        return resp.json()
    except Exception as e:
        logger.error("Ibrat Farzandlari JSON parse failed. Status: %s, Head: %s", resp.status_code, resp.text[:200])
        raise


def _ensure_optimal_limit(url: str, min_limit: int = 100) -> str:
    """Agar limit kichik bo'lsa (masalan 47), 1 ta so'rovda barchasini olish uchun limit=100 qiladi."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    try:
        cur_limit = int(query.get("limit") or 0)
    except Exception:
        cur_limit = 0
    if cur_limit < min_limit:
        query["limit"] = str(min_limit)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), parts.fragment))
    return url


def _with_page(url: str, page: int) -> str:
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


def _normalize_name(value: str) -> str:
    cleaned = value.lower()
    cleaned = re.sub(r"\bma[hx]alla(?:si)?\b", "", cleaned)
    cleaned = cleaned.replace("mahallas", "")
    cleaned = cleaned.replace("maxallas", "")
    cleaned = cleaned.replace("mahalla", "")
    cleaned = cleaned.replace("maxalla", "")
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


def _resolve_alias(api_name: str) -> IbratFarzandlariMahallaAlias:
    api_clean = (api_name or "").strip()
    api_norm = _normalize_name(api_clean)

    alias = IbratFarzandlariMahallaAlias.objects.filter(api_norm=api_norm).first()
    if not alias:
        # Core Mahalla bilan bog'lashga harakat qilamiz
        mahalla = None
        # 1. To'g'ridan-to'g'ri nom bo'yicha qidiruv
        mahalla = Mahalla.objects.filter(name__iexact=api_clean).first()

        # 2. Maxsus xaritadan qidiruv
        if not mahalla:
            mapped_name = INITIAL_ALIAS_MAPPING.get(api_clean.lower())
            if mapped_name:
                mahalla = Mahalla.objects.filter(name=mapped_name).first()

        # 3. Normallashtirilgan nom bo'yicha qidiruv
        if not mahalla:
            for m in Mahalla.objects.all():
                if _normalize_name(m.name) == api_norm:
                    mahalla = m
                    break

        alias = IbratFarzandlariMahallaAlias.objects.create(
            api_name=api_clean,
            api_norm=api_norm,
            mahalla=mahalla,
        )
    elif alias.api_name != api_clean:
        alias.api_name = api_clean
        alias.save(update_fields=["api_name", "last_seen"])

    return alias


def _extract_items(payload: dict) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return data
        for key in ("results", "items", "neighborhoods"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
    return []


def _resolve_area_name(item: dict) -> str:
    for key in ("name", "neighborhood", "title", "mahalla", "village"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Noma'lum"


def _resolve_area_id(item: dict) -> str | None:
    for key in ("id", "code", "pk", "uuid"):
        value = item.get(key)
        if value is not None:
            return str(value)
    return None


def _extract_metrics(item: dict) -> dict:
    metrics = {}
    for key, value in item.items():
        if key in ("id", "pk", "uuid", "name", "title", "mahalla"):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            metrics[key] = value
    return metrics


class IbratStatsAdapter(BaseStatsAdapter):
    snapshot_model = IbratFarzandlariStatSnapshot
    stat_model = IbratFarzandlariMahallaStat
    unknown_error_message = "Noma'lum xatolik (logni tekshiring)"
    log_unknown_error = True
    logger = logger

    def get_url(self):
        return get_ibrat_url()

    def fetch_payload(self, url):
        optimal_url = _ensure_optimal_limit(url, min_limit=100)
        session = _get_session()
        all_items: list[dict] = []
        raw_pages: list[dict] = []
        start_page = _get_start_page(optimal_url)
        page = start_page
        total_count = None
        last_updated_at = None

        for _ in range(1, 25):
            page_url = _with_page(optimal_url, page)
            raw = _fetch_json(page_url, session=session)
            raw_pages.append(raw)

            if isinstance(raw, dict):
                if total_count is None and "total_count" in raw:
                    total_count = raw.get("total_count")
                if last_updated_at is None and "last_updated_at" in raw:
                    last_updated_at = raw.get("last_updated_at")

            items = _extract_items(raw)
            if items:
                all_items.extend([i for i in items if isinstance(i, dict)])

            if total_count is not None and len(all_items) >= total_count:
                break
            if not items:
                break
            page += 1

        return {
            "data": all_items,
            "total_count": total_count or len(all_items),
            "last_updated_at": last_updated_at,
            "raw_pages": raw_pages,
        }

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
        return IbratFarzandlariMahallaStat(
            snapshot=snapshot,
            mahalla=alias.mahalla,
            area_external_id=area_external_id,
            area_name=area_name,
            metrics=metrics,
        )


_adapter = IbratStatsAdapter()


def save_ibrat_snapshot(payload: dict, source_url: str | None = None) -> IbratFarzandlariStatSnapshot:
    return _adapter.build_snapshot(payload, source_url or get_ibrat_url())


def fetch_and_store_ibrat_snapshot() -> tuple[IbratFarzandlariStatSnapshot | None, str | None]:
    return _adapter.fetch_and_store()


def build_table(
    snapshot: IbratFarzandlariStatSnapshot | None,
    mahallas: list[Mahalla] | None = None,
    youth_counts: dict[int, int] | None = None,
) -> tuple[list[str], list[dict], dict | None]:
    if not snapshot:
        return [], [], None

    rows = list(snapshot.area_stats.select_related("mahalla").all())
    alias_to_mahalla_id = {
        a.api_name: a.mahalla_id
        for a in IbratFarzandlariMahallaAlias.objects.exclude(mahalla_id__isnull=True)
    }

    row_by_mahalla_id: dict[int, dict] = {}
    for row in rows:
        mahalla_id = row.mahalla_id
        if not mahalla_id:
            mahalla_id = alias_to_mahalla_id.get((row.area_name or "").strip())
        if mahalla_id:
            u_count = row.metrics.get("user_count") or 0
            c_count = row.metrics.get("certificate_count") or 0
            if mahalla_id in row_by_mahalla_id:
                existing = row_by_mahalla_id[mahalla_id]
                existing["user_count"] += u_count
                existing["certificate_count"] += c_count
            else:
                row_by_mahalla_id[mahalla_id] = {
                    "user_count": u_count,
                    "certificate_count": c_count,
                }

    if mahallas is None:
        mahallas = list(Mahalla.objects.all().order_by("name"))

    youth_counts = youth_counts or {}

    ordered_columns = [
        "mahalla_name",
        "total_youth",
        "users_total",
        "users_ratio_percent",
        "certificates_count",
    ]
    table_rows = []
    total_youth_sum = 0
    total_users_sum = 0
    total_cert_sum = 0

    for mahalla in mahallas:
        stat_data = row_by_mahalla_id.get(mahalla.id)
        item = {"mahalla_name": mahalla.name}
        item["row_class"] = "row-missing" if stat_data is None else ""

        total_youth = youth_counts.get(mahalla.id) or 0
        users_total = stat_data.get("user_count", 0) if stat_data else 0
        certificates_count = stat_data.get("certificate_count", 0) if stat_data else 0

        item["total_youth"] = total_youth
        item["users_total"] = users_total
        item["certificates_count"] = certificates_count

        ratio_value = None
        if total_youth and users_total is not None:
            try:
                ratio_value = (float(users_total) / float(total_youth)) * 100
                item["users_ratio_percent"] = f"{ratio_value:.1f}%"
            except Exception:
                item["users_ratio_percent"] = "—"
        else:
            item["users_ratio_percent"] = "—"

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
        total_cert_sum += item["certificates_count"] or 0
        table_rows.append(item)

    def _sort_key(r):
        val = r["ratio_value"] if r["ratio_value"] is not None else 0
        return (r["ratio_value"] is None, -val)

    table_rows.sort(key=_sort_key)

    total_ratio_text = "—"
    if total_youth_sum > 0:
        total_ratio_val = (float(total_users_sum) / float(total_youth_sum)) * 100
        total_ratio_text = f"{total_ratio_val:.1f}%"

    total_row = {
        "mahalla_name": "Tuman bo'yicha jami",
        "total_youth": total_youth_sum,
        "users_total": total_users_sum,
        "users_ratio_percent": total_ratio_text,
        "certificates_count": total_cert_sum,
    }

    return ordered_columns, table_rows, total_row
