import base64
from collections import Counter, defaultdict
import contextlib
from difflib import get_close_matches
import io
from io import BytesIO
import mimetypes
import os
import re
import string
import subprocess
import time
import uuid
import logging

import pandas as pd
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView
import requests

try:
    import ddddocr
except ImportError:
    ddddocr = None  # type: ignore[assignment]

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment]

from core.models import Mahalla, Yosh
from .models import FiveInitiativeApplicationEntry, FiveInitiativeApplicationSnapshot, FiveInitiativeSvodNorm

logger = logging.getLogger(__name__)

CAPTCHA_URL = "https://api.5tashabbus.uz/Account/GenerateCaptcha"
ATHLETE_INFO_URL = "https://api.5tashabbus.uz/Account/GetAthleteInfoForRegistration"
ATTACH_FILE_URL = "https://api.5tashabbus.uz/FileManage/Attach"
INSERT_REGISTRATION_URL = "https://api.5tashabbus.uz/Account/InsertRegistrationOfAthlete"
ATHLETE_INFO_BASE_PARAMS = {
    "lang": "uz_latn",
    "initiativTypeId": "1",
}
DEFAULT_ATTEMPTS = int(os.environ.get("FIVE_TASHABBUS_CAPTCHA_ATTEMPTS", "1"))
DEFAULT_ATTEMPT_WAIT_SECONDS = float(os.environ.get("FIVE_TASHABBUS_CAPTCHA_WAIT_SECONDS", "0"))
SQLITE_IN_MAX_VARS = 900
_LOCAL_OCR = None
_LOCAL_OCR_INIT_ERROR = None
_EXTERNAL_OCR_PYTHON = os.environ.get(
    "FIVE_TASHABBUS_OCR_PYTHON",
    r"D:\dev\projects\5tashabbus\.venv\Scripts\python.exe",
)
_EXTERNAL_OCR_PROJECT = os.environ.get(
    "FIVE_TASHABBUS_OCR_PROJECT",
    r"D:\dev\projects\5tashabbus",
)
_USE_OPENAI_OCR = os.environ.get("FIVE_TASHABBUS_USE_OPENAI_OCR", "").strip().lower() in {"1", "true", "yes", "on"}

SPORTTYPE_CATEGORY_CHOICES = [
    {"id": 155, "name": "Sport yo'nalishi"},
    {"id": 157, "name": "Madaniyat va sa'nat yo'nalishi"},
    {"id": 158, "name": "Kibersport musobaqalari"},
    {"id": 159, "name": "Intellektual o'yinlar yo'nalishi"},
    {"id": 161, "name": "Kitobxonlik yo'nalishi"},
    {"id": 571, "name": "Adaptiv"},
    {"id": 156, "name": "Zamonaviy kasblar"},
]


REQUIRED_IMPORT_HEADERS = [
    "\u041e\u0431\u043b\u0430\u0441\u0442\u044c",
    "\u0420\u0430\u0439\u043e\u043d (\u0433\u043e\u0440\u043e\u0434)",
    "\u0421\u0435\u043a\u0442\u043e\u0440",
    "\u041c\u0430\u04b3\u0430\u043b\u043b\u044f",
    "\u0423\u0447\u0430\u0441\u0442\u043d\u0438\u043a \u0424.\u0418.\u041e",
    "\u041f\u0418\u041d\u0424\u041b",
    "\u041f\u043e\u043b",
    "\u0412\u043e\u0437\u0440\u0430\u0441\u0442\u043d\u0430\u044f \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f",
    "\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f \u0432\u044b\u0431\u043e\u0440\u0430",
    "\u041d\u0430\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435 \u0432\u044b\u0431\u043e\u0440\u0430",
]

COL_REGION = REQUIRED_IMPORT_HEADERS[0]
COL_DISTRICT = REQUIRED_IMPORT_HEADERS[1]
COL_SECTOR = REQUIRED_IMPORT_HEADERS[2]
COL_MAHALLA = REQUIRED_IMPORT_HEADERS[3]
COL_PARTICIPANT = REQUIRED_IMPORT_HEADERS[4]
COL_PINFL = REQUIRED_IMPORT_HEADERS[5]
COL_GENDER = REQUIRED_IMPORT_HEADERS[6]
COL_AGE = REQUIRED_IMPORT_HEADERS[7]
COL_CATEGORY = REQUIRED_IMPORT_HEADERS[8]
COL_DIRECTION = REQUIRED_IMPORT_HEADERS[9]

MAHALLA_ALIAS_MAP = {
    "buyuksiymo": "buyuksimo",
    "gofurgulom": "ggofur",
    "oybek": "oybeknomli",
    "qirtepa": "kirtepa",
    "shoduhurram": "shoduxurram",
    "temirchimaskan": "temirchimaskani",
    "yuqorishovat": "yuqorishovot",
    "yangibozar": "yangibozor",
}


def _detect_header_row(df_raw):
    for idx in range(min(30, len(df_raw))):
        row = [str(v).strip() for v in df_raw.iloc[idx].tolist() if pd.notna(v)]
        if COL_PINFL in row and COL_PARTICIPANT in row and COL_DIRECTION in row:
            return idx
    return None


def _load_import_dataframe(uploaded_file):
    raw = uploaded_file.read()
    if not raw:
        return None, ["Fayl bo'sh yoki o'qib bo'lmadi."]
    uploaded_file.seek(0)

    try:
        df_raw = pd.read_excel(BytesIO(raw), header=None)
    except Exception:
        return None, ["XLSX fayl formatini o'qib bo'lmadi."]

    header_row = _detect_header_row(df_raw)
    if header_row is None:
        return None, ["Sarlavha qatori topilmadi. Fayl formati noto'g'ri."]

    try:
        df = pd.read_excel(BytesIO(raw), header=header_row)
    except Exception:
        return None, ["Sarlavha asosida jadvalni o'qib bo'lmadi."]

    df.columns = [str(col).strip() for col in df.columns]
    missing = [col for col in REQUIRED_IMPORT_HEADERS if col not in df.columns]
    if missing:
        return None, [f"Majburiy ustunlar topilmadi: {', '.join(missing)}"]

    df = df[df[COL_PINFL].notna() & df[COL_PARTICIPANT].notna() & df[COL_MAHALLA].notna()].copy()
    if df.empty:
        return None, ["Yuklangan faylda import uchun satr topilmadi."]

    return df, []


def _validate_import_dataframe(df):
    errors = []
    pin = df[COL_PINFL].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    valid_pin = pin.str.fullmatch(r"\d{14}")
    invalid_count = int((~valid_pin).sum())
    if invalid_count:
        errors.append(f"PINFL noto'g'ri formatdagi satrlar: {invalid_count} ta.")

    if df[COL_DIRECTION].isna().sum():
        errors.append("Yo'nalish ustunida bo'sh qiymatlar bor.")
    if df[COL_CATEGORY].isna().sum():
        errors.append("Kategoriya ustunida bo'sh qiymatlar bor.")

    return errors


def _normalize_mahalla_name(value):
    cleaned = (value or "").strip().lower()
    cleaned = (
        cleaned.replace("`", "'")
        .replace("вЂ™", "'")
        .replace("К»", "'")
        .replace("вЂ", "'")
        .replace("Кј", "'")
        .replace("o'", "o")
        .replace("g'", "g")
        .replace("oК»", "o")
        .replace("gК»", "g")
        .replace("oвЂ", "o")
        .replace("gвЂ", "g")
        .replace("С…", "x")
        .replace("Ті", "h")
    )
    cleaned = cleaned.replace("mahallasi", "").replace("mahalla", "").replace("nomli", "")
    cleaned = re.sub(r"\bm\.?f\.?y\b", "", cleaned)
    cleaned = re.sub(r"\bmf\b", "", cleaned)
    cleaned = re.sub(r"[^a-z0-9]+", "", cleaned)
    return cleaned


def _build_mahalla_resolver():
    by_norm = {}
    for mahalla in Mahalla.objects.all():
        norm = _normalize_mahalla_name(mahalla.name)
        if norm:
            by_norm[norm] = mahalla.name
    return by_norm


def _resolve_source_mahalla_name(raw_name, by_norm):
    raw = (raw_name or "").strip()
    if not raw:
        return "Mahalla ko'rsatilmagan"

    norm = _normalize_mahalla_name(raw)
    if not norm:
        return raw

    direct = by_norm.get(norm)
    if direct:
        return direct

    alias_norm = MAHALLA_ALIAS_MAP.get(norm)
    if alias_norm:
        aliased = by_norm.get(alias_norm)
        if aliased:
            return aliased

    best = get_close_matches(norm, list(by_norm.keys()), n=1, cutoff=0.82)
    if best:
        return by_norm[best[0]]
    return raw


def _build_pinfl_mahalla_map(entries):
    pinfls = {entry.pinfl for entry in entries if entry.pinfl}
    if not pinfls:
        return {}
    return {
        row.jshshir: row.mahalla.name
        for row in _fetch_yosh_by_pinfls(pinfls).values()
        if row.mahalla_id
    }


def _aggregate_rows(entries, mahalla_name_getter):
    rows_by_mahalla = defaultdict(
        lambda: {
            "applications_count": 0,
            "pinfl_set": set(),
            "male_count": 0,
            "female_count": 0,
            "category_counter": Counter(),
            "direction_counter": Counter(),
            "age_counter": Counter(),
        }
    )

    for item in entries:
        key = mahalla_name_getter(item)
        if not key:
            continue
        bucket = rows_by_mahalla[key]
        bucket["applications_count"] += 1
        bucket["pinfl_set"].add(item.pinfl)

        gender = (item.gender or "").strip().lower()
        if "жен" in gender or "female" in gender or "ayol" in gender or "Р¶РµРЅ" in gender:
            bucket["female_count"] += 1
        elif "муж" in gender or "male" in gender or "erkak" in gender or "РјСѓР¶" in gender:
            bucket["male_count"] += 1

        if item.selection_category:
            bucket["category_counter"][item.selection_category] += 1
        if item.direction:
            bucket["direction_counter"][item.direction] += 1
        if item.age_category:
            bucket["age_counter"][item.age_category] += 1

    result = []
    for mahalla_name, data in rows_by_mahalla.items():
        result.append(
            {
                "mahalla_name": mahalla_name,
                "applications_count": data["applications_count"],
                "unique_participants_count": len(data["pinfl_set"]),
                "male_count": data["male_count"],
                "female_count": data["female_count"],
                "top_categories": data["category_counter"].most_common(3),
                "top_directions": data["direction_counter"].most_common(3),
                "category_counter": dict(data["category_counter"]),
                "direction_counter": dict(data["direction_counter"]),
                "age_counter": dict(data["age_counter"]),
            }
        )
    result.sort(key=lambda x: (-x["applications_count"], x["mahalla_name"]))
    return result


def _aggregate_source_rows(entries):
    source_resolver = _build_mahalla_resolver()
    return _aggregate_rows(
        entries,
        mahalla_name_getter=lambda item: _resolve_source_mahalla_name(item.mahalla_name_raw, source_resolver),
    )


def _aggregate_system_rows(entries):
    pinfl_mahalla_map = _build_pinfl_mahalla_map(entries)
    return _aggregate_rows(entries, mahalla_name_getter=lambda item: pinfl_mahalla_map.get(item.pinfl))


def _count_not_found_applications_by_source_mahalla(entries):
    source_resolver = _build_mahalla_resolver()
    pinfls = {entry.pinfl for entry in entries if entry.pinfl}
    found_pinfls = set(_fetch_yosh_by_pinfls(pinfls).keys()) if pinfls else set()

    counts = defaultdict(int)
    for item in entries:
        source_name = _resolve_source_mahalla_name(item.mahalla_name_raw, source_resolver)
        if not source_name:
            continue
        if item.pinfl not in found_pinfls:
            counts[source_name] += 1
    return dict(counts)


def _summarize_rows(rows):
    return {
        "applications_count": sum(int(row.get("applications_count") or 0) for row in rows),
        "unique_participants_count": sum(int(row.get("unique_participants_count") or 0) for row in rows),
    }


def _build_method_diff_rows(source_rows, system_rows, not_found_by_source_mahalla=None):
    source_map = {row["mahalla_name"]: row for row in source_rows}
    system_map = {row["mahalla_name"]: row for row in system_rows}
    names = sorted(set(source_map.keys()) | set(system_map.keys()))
    not_found_by_source_mahalla = not_found_by_source_mahalla or {}

    rows = []
    for name in names:
        source = source_map.get(name, {})
        system = system_map.get(name, {})
        source_apps = int(source.get("applications_count", 0))
        system_apps = int(system.get("applications_count", 0))
        source_unique = int(source.get("unique_participants_count", 0))
        system_unique = int(system.get("unique_participants_count", 0))
        delta_apps = system_apps - source_apps
        delta_unique = system_unique - source_unique
        rows.append(
            {
                "mahalla_name": name,
                "source_applications": source_apps,
                "system_applications": system_apps,
                "delta_applications": delta_apps,
                "source_unique": source_unique,
                "system_unique": system_unique,
                "delta_unique": delta_unique,
                "not_found_applications": int(not_found_by_source_mahalla.get(name, 0)),
                "delta_applications_class": "text-success fw-semibold"
                if delta_apps > 0
                else ("text-danger fw-semibold" if delta_apps < 0 else "text-muted"),
                "delta_unique_class": "text-success fw-semibold"
                if delta_unique > 0
                else ("text-danger fw-semibold" if delta_unique < 0 else "text-muted"),
            }
        )
    rows.sort(
        key=lambda row: (
            -(abs(row["delta_applications"]) + abs(row["delta_unique"]) + row["not_found_applications"]),
            row["mahalla_name"],
        )
    )
    return rows



def _build_compare_rows(left_rows, right_rows):
    left_map = {r["mahalla_name"]: r for r in left_rows}
    right_map = {r["mahalla_name"]: r for r in right_rows}
    names = sorted(set(left_map.keys()) | set(right_map.keys()))

    rows = []
    for name in names:
        left = left_map.get(name, {})
        right = right_map.get(name, {})
        left_apps = int(left.get("applications_count", 0))
        right_apps = int(right.get("applications_count", 0))
        left_unique = int(left.get("unique_participants_count", 0))
        right_unique = int(right.get("unique_participants_count", 0))
        rows.append(
            {
                "mahalla_name": name,
                "left_applications": left_apps,
                "right_applications": right_apps,
                "delta_applications": right_apps - left_apps,
                "left_unique": left_unique,
                "right_unique": right_unique,
                "delta_unique": right_unique - left_unique,
                "delta_applications_class": "text-success fw-semibold"
                if (right_apps - left_apps) > 0
                else ("text-danger fw-semibold" if (right_apps - left_apps) < 0 else "text-muted"),
                "delta_unique_class": "text-success fw-semibold"
                if (right_unique - left_unique) > 0
                else ("text-danger fw-semibold" if (right_unique - left_unique) < 0 else "text-muted"),
                "sort_score": max(abs(right_apps - left_apps), abs(right_unique - left_unique)),
            }
        )
    rows.sort(key=lambda r: (-r["sort_score"], -abs(r["delta_applications"]), r["mahalla_name"]))
    return rows


def _build_compare_summary(compare_rows):
    if not compare_rows:
        return {
            "left_applications": 0,
            "right_applications": 0,
            "delta_applications": 0,
            "left_unique": 0,
            "right_unique": 0,
            "delta_unique": 0,
        }
    left_apps = sum(r["left_applications"] for r in compare_rows)
    right_apps = sum(r["right_applications"] for r in compare_rows)
    left_unique = sum(r["left_unique"] for r in compare_rows)
    right_unique = sum(r["right_unique"] for r in compare_rows)
    return {
        "left_applications": left_apps,
        "right_applications": right_apps,
        "delta_applications": right_apps - left_apps,
        "left_unique": left_unique,
        "right_unique": right_unique,
        "delta_unique": right_unique - left_unique,
    }


def _request_with_proxy_fallback(method: str, url: str, session=None, **kwargs):
    session = session or requests.Session()
    try:
        return session.request(method, url, **kwargs)
    except requests.exceptions.ProxyError:
        session.trust_env = False
        return session.request(method, url, **kwargs)


def _normalize_letters(text: str) -> str:
    latin = set(string.ascii_letters)
    return "".join(ch for ch in str(text or "") if ch in latin)[:4].upper()


def _init_local_ocr():
    global _LOCAL_OCR, _LOCAL_OCR_INIT_ERROR
    if _LOCAL_OCR is not None or _LOCAL_OCR_INIT_ERROR is not None:
        return
    if ddddocr is None or Image is None:
        _LOCAL_OCR_INIT_ERROR = "ddddocr yoki Pillow topilmadi."
        return
    try:
        if not hasattr(Image, "ANTIALIAS") and hasattr(Image, "Resampling"):
            Image.ANTIALIAS = Image.Resampling.LANCZOS  # type: ignore[attr-defined]
        with contextlib.redirect_stdout(io.StringIO()):
            _LOCAL_OCR = ddddocr.DdddOcr()
    except Exception as exc:
        _LOCAL_OCR_INIT_ERROR = str(exc)


def _read_4_letters_with_local_ocr(png_bytes: bytes):
    _init_local_ocr()
    if _LOCAL_OCR is None:
        return None
    try:
        raw_text = _LOCAL_OCR.classification(png_bytes)
    except Exception:
        return None
    letters = _normalize_letters(raw_text)
    return letters if len(letters) == 4 else None


def _read_4_letters_with_gpt(image_b64: str) -> str:
    api_key = (getattr(settings, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")).strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY topilmadi.")

    base_url = (
        os.environ.get("CAPTCHA_OCR_BASE_URL", "")
        or os.environ.get("OPENAI_BASE_URL", "")
        or "https://api.openai.com/v1"
    ).rstrip("/")
    model = (
        os.environ.get("CAPTCHA_OCR_MODEL")
        or "gpt-4o-mini"
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Captcha dagi 4 ta katta lotin harfini qaytar. Faqat 4 harf."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}", "detail": "high"}},
                ],
            }
        ],
        "max_tokens": 8,
        "temperature": 0,
    }
    response = _request_with_proxy_fallback(
        "POST",
        f"{base_url}/chat/completions",
        headers=headers,
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    text = response.json()["choices"][0]["message"]["content"].strip()
    letters = _normalize_letters(text)
    if len(letters) != 4:
        raise ValueError(f"Captcha 4 harf bo'lib o'qilmadi: {text}")
    return letters


def _read_4_letters_with_external_ocr(image_b64: str):
    if not os.path.exists(_EXTERNAL_OCR_PYTHON):
        return None
    command = [
        _EXTERNAL_OCR_PYTHON,
        "-c",
        (
            "import sys; "
            f"sys.path.insert(0, r'{_EXTERNAL_OCR_PROJECT}'); "
            "from gpt import read_4_letters_from_png; "
            "print(read_4_letters_from_png(sys.stdin.read().strip()))"
        ),
    ]
    try:
        env = {
            **os.environ,
            "OCR_MODE": "only_ocr",
            "OCR_GPT_FALLBACK": "0",
        }
        result = subprocess.run(
            command,
            input=image_b64,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
            env=env,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    letters = _normalize_letters(result.stdout.strip())
    return letters if len(letters) == 4 else None


def _read_4_letters_from_png(image_text: str) -> str:
    image_b64 = (image_text or "").strip()
    if image_b64.startswith("data:image/") and "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]
    image_b64 = "".join(image_b64.split())
    missing = (-len(image_b64)) % 4
    if missing:
        image_b64 += "=" * missing
    try:
        png_bytes = base64.b64decode(image_b64, validate=True)
    except Exception as exc:
        raise ValueError("Captcha base64 noto'g'ri.") from exc
    if len(png_bytes) < 24 or png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Captcha PNG formatda emas.")

    letters = _read_4_letters_with_local_ocr(png_bytes)
    if letters:
        return letters
    letters = _read_4_letters_with_external_ocr(image_b64)
    if letters:
        return letters
    if not _USE_OPENAI_OCR:
        if _LOCAL_OCR_INIT_ERROR:
            raise ValueError(f"Lokal OCR ishlamadi: {_LOCAL_OCR_INIT_ERROR}")
        raise ValueError("Captcha lokal OCR bilan o'qilmadi.")
    if _LOCAL_OCR_INIT_ERROR and not getattr(settings, "OPENAI_API_KEY", ""):
        raise ValueError(f"Lokal OCR ishlamadi: {_LOCAL_OCR_INIT_ERROR}")
    return _read_4_letters_with_gpt(image_b64)


def _build_captcha_url(phone_number: str, request_id: str) -> str:
    return f"{CAPTCHA_URL}?id={request_id}&phoneNumber={phone_number}"


def _get_captcha(phone_number: str, session, request_id: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Request-Id": request_id,
    }
    try:
        response = _request_with_proxy_fallback(
            "GET",
            _build_captcha_url(phone_number, request_id),
            headers=headers,
            session=session,
            timeout=10,
        )
        response.raise_for_status()
        return response.json(), ""
    except requests.exceptions.RequestException as exc:
        return None, f"Internet xatoligi (captcha): {exc}"
    except ValueError:
        return None, "Sayt xatoligi (captcha): javob JSON emas"


def _get_athlete_info(
    captcha_text: str,
    document_series: str,
    document_number: str,
    date_of_birth: str,
    phone_number: str,
    identity_document_id: int,
    session,
    request_id: str,
):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Request-Id": request_id,
    }

    params = dict(ATHLETE_INFO_BASE_PARAMS)
    params.update(
        {
            "identityDocumentId": str(identity_document_id),
            "DocumentSeries": document_series,
            "DocumentNumber": document_number,
            "DateOfBirth": date_of_birth,
            "captchaText": captcha_text,
            "phoneNumber": phone_number,
        }
    )
    try:
        response = _request_with_proxy_fallback(
            "POST",
            ATHLETE_INFO_URL,
            headers=headers,
            data=params,
            session=session,
            timeout=15,
        )
        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            return None, "Sayt xatoligi (GetAthleteInfo): javob JSON emas"
        if response.status_code >= 400 and isinstance(data, dict):
            return data, ""
        response.raise_for_status()
        return data, ""
    except requests.exceptions.RequestException as exc:
        return None, f"Internet xatoligi (GetAthleteInfo): {exc}"


def _wait_before_next_attempt(attempt: int, attempts: int) -> None:
    if attempt < max(1, attempts):
        time.sleep(DEFAULT_ATTEMPT_WAIT_SECONDS)


def _extract_message(payload):
    if not isinstance(payload, dict):
        return str(payload)
    for key in ("message", "error", "detail"):
        value = payload.get(key)
        if value:
            return str(value)
    errors = payload.get("errors")
    if errors:
        return str(errors)
    result = payload.get("result")
    if isinstance(result, dict):
        for key in ("message", "error", "detail"):
            value = result.get(key)
            if value:
                return str(value)
    return ""


def _mask_document(value):
    text = str(value or "").strip()
    if len(text) <= 4:
        return text
    return f"{text[:2]}***{text[-2:]}"


def _parse_passport(passport_value):
    cleaned = re.sub(r"\s+", "", str(passport_value or "")).upper()
    if len(cleaned) < 3:
        return None, None
    series = cleaned[:2]
    number = "".join(ch for ch in cleaned[2:] if ch.isdigit())
    if len(series) != 2 or not series.isalpha() or not number:
        return None, None
    return series, number


def _parse_guvohnoma(guvohnoma_value):
    cleaned = re.sub(r"[\s\-]+", "", str(guvohnoma_value or "")).upper()
    if len(cleaned) < 4:
        return None, None

    match = re.fullmatch(r"(VIII|VII|III|VI|IV|IX|II|V|I)([A-Z]{2})(\d+)", cleaned)
    if not match:
        return None, None

    roman_part, letter_part, number_part = match.groups()
    return f"{roman_part}-{letter_part}", number_part


def _parse_identity_document(yosh):
    document_series, document_number = _parse_passport(yosh.passport_number)
    if document_series and document_number:
        return document_series, document_number, 2

    document_series, document_number = _parse_guvohnoma(yosh.guvohnoma_raqami)
    if document_series and document_number:
        return document_series, document_number, 1

    return None, None, None


def _format_phone_number(raw_phone: str):
    digits = re.sub(r"\D+", "", str(raw_phone or ""))
    if not digits:
        return None
    if digits.startswith("998") and len(digits) == 12:
        core = digits[3:]
    elif len(digits) == 9:
        core = digits
    else:
        return None

    return f"+998-{core[0:2]}-{core[2:5]}-{core[5:7]}-{core[7:9]}"


def _can_submit_application(user):
    if not user or not user.is_authenticated:
        return False
    return user.has_perm("beshtashabbus.submit_application")


def _gender_id_from_pinfl(pinfl: str):
    if not pinfl:
        return None
    first = str(pinfl).strip()[:1]
    if first in {"3", "5"}:
        return 1
    if first in {"4", "6"}:
        return 2
    return None


def _coalesce_id(*values):
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, float) and value.is_integer() and int(value) > 0:
            return int(value)
        if isinstance(value, str):
            text = value.strip()
            if text.isdigit() and int(text) > 0:
                return int(text)
    return None


def _coalesce_text(*values):
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _chunked(iterable, size=SQLITE_IN_MAX_VARS):
    items = list(iterable)
    for idx in range(0, len(items), size):
        yield items[idx:idx + size]


def _fetch_yosh_by_pinfls(pinfls):
    result = {}
    for chunk in _chunked([pinfl for pinfl in pinfls if pinfl]):
        for item in Yosh.objects.select_related("mahalla").filter(jshshir__in=chunk):
            result[item.jshshir] = item
    return result


def _count_existing_yosh_pinfls(pinfls):
    matched = set()
    for chunk in _chunked([pinfl for pinfl in pinfls if pinfl]):
        matched.update(
            Yosh.objects.filter(jshshir__in=chunk).values_list("jshshir", flat=True).distinct()
        )
    return len(matched)


def _pick_primary_citizen(athlete_result):
    citizens = athlete_result.get("CitizensInfoTables")
    if not isinstance(citizens, list):
        return {}

    for item in citizens:
        if isinstance(item, dict) and (item.get("isactiveaddress") is True or item.get("ispermanentaddress") is True):
            return item

    for item in citizens:
        if isinstance(item, dict):
            return item
    return {}


def _resolve_location(athlete_result):
    citizen = _pick_primary_citizen(athlete_result)
    return {
        "oblastid": _coalesce_id(athlete_result.get("oblastid"), citizen.get("oblastid"), 14),
        "oblastname": _coalesce_text(athlete_result.get("oblastname"), citizen.get("oblastname"), "Xorazm viloyati"),
        "regionid": _coalesce_id(athlete_result.get("regionid"), citizen.get("regionid"), 193),
        "regionname": _coalesce_text(athlete_result.get("regionname"), citizen.get("regionname"), "Xazorasp tumani"),
        "mfyid": _coalesce_id(athlete_result.get("mfyid"), citizen.get("mfyid"), 21997),
        "mfyname": _coalesce_text(athlete_result.get("mfyname"), citizen.get("mfyname"), "MING OTLIQLAR"),
    }


def _build_registration_payload(
    athlete_result,
    document_series,
    document_number,
    identity_document_id,
    sporttypeids,
    sporttypecategoryid,
    sporttypecategoryname,
    phonenumber,
    photo_payload=None,
):
    photo = photo_payload or (athlete_result.get("photo") if isinstance(athlete_result.get("photo"), dict) else {})
    location = _resolve_location(athlete_result)

    if not isinstance(identity_document_id, int) or identity_document_id <= 0:
        identity_document_id = athlete_result.get("identitydocumentid")
        if not isinstance(identity_document_id, int) or identity_document_id <= 0:
            identity_document_id = 2

    return {
        "id": 0,
        "healthtypeid": athlete_result.get("healthtypeid", 1),
        "detail": str(athlete_result.get("detail") or ""),
        "oblastid": location["oblastid"],
        "oblastname": location["oblastname"],
        "regionid": location["regionid"],
        "regionname": location["regionname"],
        "mfyid": location["mfyid"],
        "mfyname": location["mfyname"],
        "regionsectorid": athlete_result.get("regionsectorid"),
        "regionsectorname": str(athlete_result.get("regionsectorname") or ""),
        "youthleaderpersonid": athlete_result.get("youthleaderpersonid"),
        "familyname": str(athlete_result.get("familyname") or ""),
        "firstname": str(athlete_result.get("firstname") or ""),
        "lastname": str(athlete_result.get("lastname") or ""),
        "shortname": str(athlete_result.get("shortname") or ""),
        "fullname": str(athlete_result.get("fullname") or ""),
        "dateofbirth": str(athlete_result.get("dateofbirth") or ""),
        "pinfl": str(athlete_result.get("pinfl") or ""),
        "genderid": athlete_result.get("genderid"),
        "gendername": str(athlete_result.get("gendername") or ""),
        "identitydocumentid": identity_document_id,
        "identitydocumentname": athlete_result.get("identitydocumentname"),
        "documentseries": document_series,
        "documentnumber": document_number,
        "sporttypeids": sporttypeids,
        "canSave": bool(athlete_result.get("CanSave", athlete_result.get("canSave", True))),
        "agecategoryid": None,
        "sporttypecategoryid": sporttypecategoryid,
        "sporttypecategoryname": sporttypecategoryname,
        "isimport": True,
        "initiativtypeid": athlete_result.get("initiativtypeid", 1),
        "initiativtypename": str(athlete_result.get("initiativtypename") or ""),
        "userId": 0,
        "CitizensInfoTables": {
            "mfyid": None,
            "mfyname": "",
        },
        "eduSchoolInfo": {
            "educationlanguageid": 0,
            "educationlanguagename": "",
            "enddate": "",
            "oblastid": 0,
            "oblastname": "",
            "organizationid": 0,
            "organizationname": "",
            "orgschoolgradeid": 0,
            "orgschoolgradename": "",
            "regionid": 0,
            "regionname": "",
            "schoolgradeid": 0,
            "schoolgradename": "",
            "startdate": "",
        },
        "orgHighEduInfo": {
            "coursecode": "",
            "coursename": "",
            "facultycode": "",
            "facultyname": "",
            "hemisid": 0,
            "id": 0,
            "oblastid": 0,
            "oblastname": "",
            "organizationid": 0,
            "organizationname": "",
            "ownerid": 0,
            "regionid": 0,
            "regionname": "",
            "specialitycode": "",
            "specialityname": "",
        },
        "photo": {
            "id": int(photo.get("id", 0) or 0),
            "ownerid": int(photo.get("ownerid", 0) or 0),
            "attachmentfileid": str(photo.get("attachmentfileid") or ""),
            "attachmentfilename": str(photo.get("attachmentfilename") or ""),
            "attachmentfiletype": str(photo.get("attachmentfiletype") or ""),
            "isphoto": bool(photo.get("isphoto", True)),
            "statusid": int(photo.get("statusid", 0) or 0),
            "Status": 1,
        },
        "phonenumber": phonenumber,
    }


def _attach_yosh_photo(yosh, session, identity_document_id):
    if identity_document_id != 1:
        return None, ""

    file_bytes = None
    filename = None
    default_photo_path = os.path.join(settings.BASE_DIR, "1.jpg")
    if not os.path.exists(default_photo_path):
        return None, "1.jpg fayli topilmadi."
    try:
        with open(default_photo_path, "rb") as file_obj:
            file_bytes = file_obj.read()
        filename = "1.jpg"
    except Exception as exc:
        return None, f"1.jpg ni o'qib bo'lmadi: {exc}"

    if not file_bytes:
        return None, "Rasm bo'sh."

    filename = filename or "1.jpg"
    content_type = mimetypes.guess_type(filename)[0] or "image/jpeg"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    files = {
        "attachfile": (filename, file_bytes, content_type),
    }
    try:
        response = _request_with_proxy_fallback(
            "POST",
            ATTACH_FILE_URL,
            headers=headers,
            files=files,
            session=session,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as exc:
        return None, f"Internet xatoligi (Attach): {exc}"
    except ValueError:
        return None, "Attach javobi JSON emas"

    attachment_file_id = str(data.get("id") or "").strip()
    if not attachment_file_id:
        return None, f"Attach javobi noto'g'ri: {data}"

    return {
        "id": 0,
        "ownerid": 0,
        "attachmentfileid": attachment_file_id,
        "attachmentfilename": str(data.get("imagetext") or filename).strip(),
        "attachmentfiletype": str(data.get("imagetype") or content_type).strip(),
        "isphoto": True,
        "statusid": 0,
        "Status": 1,
    }, ""


def _resolve_snapshot_meta(snapshot):
    raw_meta = snapshot.raw_meta or {}
    has_full_meta = (
        raw_meta.get("rows_total") is not None
        and raw_meta.get("unique_pinfl") is not None
        and raw_meta.get("matched_pinfl") is not None
        and raw_meta.get("not_found_pinfl") is not None
    )
    if has_full_meta:
        return {
            "rows_total": int(raw_meta.get("rows_total") or 0),
            "unique_pinfl": int(raw_meta.get("unique_pinfl") or 0),
            "matched_pinfl": int(raw_meta.get("matched_pinfl") or 0),
            "not_found_pinfl": int(raw_meta.get("not_found_pinfl") or 0),
        }

    entries_qs = FiveInitiativeApplicationEntry.objects.filter(snapshot=snapshot)
    rows_total = entries_qs.count()
    pinfl_list = list(
        entries_qs.exclude(pinfl__isnull=True).exclude(pinfl="").values_list("pinfl", flat=True).distinct()
    )
    unique_pinfl = len(pinfl_list)
    matched_pinfl = _count_existing_yosh_pinfls(pinfl_list) if pinfl_list else 0
    not_found_pinfl = max(unique_pinfl - matched_pinfl, 0)
    return {
        "rows_total": rows_total,
        "unique_pinfl": unique_pinfl,
        "matched_pinfl": matched_pinfl,
        "not_found_pinfl": not_found_pinfl,
    }


class FiveInitiativeApplicationUploadView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = "beshtashabbus/application_tabs.html"

    def test_func(self):
        return getattr(self.request.user, "is_site_admin", False)

    def get(self, request):
        # reuse the context from SvodTabsView for consistency
        view = FiveInitiativeApplicationSvodTabsView()
        view.request = request
        view.kwargs = {}
        context = view.get_context_data()
        context["active_tab"] = "upload" # force upload tab
        return render(request, self.template_name, context)

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        year = request.POST.get("year", "2026").strip()
        try:
            year = int(year)
        except Exception:
            messages.error(request, "Yil noto'g'ri formatda.")
            return redirect("beshtashabbus:application_upload")

        if not uploaded_file:
            messages.error(request, "XLSX fayl tanlanmadi.")
            return redirect("beshtashabbus:application_upload")
        if not uploaded_file.name.lower().endswith(".xlsx"):
            messages.error(request, "Faqat .xlsx format qabul qilinadi.")
            return redirect("beshtashabbus:application_upload")

        df, parse_errors = _load_import_dataframe(uploaded_file)
        if parse_errors:
            for err in parse_errors:
                messages.error(request, err)
            return redirect("beshtashabbus:application_upload")

        validation_errors = _validate_import_dataframe(df)
        if validation_errors:
            for err in validation_errors:
                messages.error(request, err)
            return redirect("beshtashabbus:application_upload")

        unique_pinfls = set()
        for _idx, row in df.iterrows():
            pinfl = str(row.get(COL_PINFL, "")).replace(".0", "").strip()
            unique_pinfls.add(pinfl)

        yosh_by_pinfl = _fetch_yosh_by_pinfls(unique_pinfls)

        not_found_pinfls = set()
        entries = []

        for _idx, row in df.iterrows():
            raw_mahalla = str(row.get(COL_MAHALLA, "")).strip()
            pinfl = str(row.get(COL_PINFL, "")).replace(".0", "").strip()
            yosh = yosh_by_pinfl.get(pinfl)
            mahalla = yosh.mahalla if yosh else None
            if not yosh:
                not_found_pinfls.add(pinfl)
            entries.append(
                {
                    "region": str(row.get(COL_REGION, "")).strip(),
                    "district": str(row.get(COL_DISTRICT, "")).strip(),
                    "sector": str(row.get(COL_SECTOR, "")).strip(),
                    "mahalla": mahalla,
                    "mahalla_name_raw": raw_mahalla,
                    "participant_name": str(row.get(COL_PARTICIPANT, "")).strip(),
                    "pinfl": pinfl,
                    "gender": str(row.get(COL_GENDER, "")).strip(),
                    "age_category": str(row.get(COL_AGE, "")).strip(),
                    "selection_category": str(row.get(COL_CATEGORY, "")).strip(),
                    "direction": str(row.get(COL_DIRECTION, "")).strip(),
                }
            )

        with transaction.atomic():
            snapshot = FiveInitiativeApplicationSnapshot.objects.create(
                year=year,
                source_file_name=uploaded_file.name,
                uploaded_by=request.user,
                raw_meta={
                    "rows_total": len(entries),
                    "unique_pinfl": len(unique_pinfls),
                    "matched_pinfl": len(unique_pinfls - not_found_pinfls),
                    "not_found_pinfl": len(not_found_pinfls),
                },
            )
            FiveInitiativeApplicationEntry.objects.bulk_create(
                [FiveInitiativeApplicationEntry(snapshot=snapshot, **entry) for entry in entries],
                batch_size=1000,
            )

        messages.success(
            request,
            (
                f"Snapshot saqlandi: {len(entries)} ta ariza. "
                f"Topilgan PINFL: {snapshot.raw_meta.get('matched_pinfl', 0)}, "
                f"topilmagan PINFL: {snapshot.raw_meta.get('not_found_pinfl', 0)}."
            ),
        )
        return redirect("beshtashabbus:application_svod")


class FiveInitiativeApplicationSvodTabsView(LoginRequiredMixin, TemplateView):
    template_name = "beshtashabbus/application_tabs.html"
    default_tab = "svod"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_tab = self.request.GET.get("tab", self.default_tab)
        
        snapshots = list(FiveInitiativeApplicationSnapshot.objects.all()[:50])
        for s in snapshots:
            s.display_meta = _resolve_snapshot_meta(s)
        current_snapshot = snapshots[0] if snapshots else None
        
        # Snapshot ichida ikkita svod:
        # 1) Fayldagi mahalla bo'yicha
        # 2) PINFL -> tizimdagi yosh mahallasi bo'yicha
        source_rows = []
        system_rows = []
        method_diff_rows = []
        not_found_by_source_mahalla = {}
        source_summary = {"applications_count": 0, "unique_participants_count": 0}
        system_summary = {"applications_count": 0, "unique_participants_count": 0}
        if current_snapshot:
            current_entries = list(
                FiveInitiativeApplicationEntry.objects.filter(snapshot=current_snapshot).select_related("mahalla")
            )
            source_rows = _aggregate_source_rows(current_entries)
            system_rows = _aggregate_system_rows(current_entries)
            not_found_by_source_mahalla = _count_not_found_applications_by_source_mahalla(current_entries)
            method_diff_rows = _build_method_diff_rows(
                source_rows,
                system_rows,
                not_found_by_source_mahalla=not_found_by_source_mahalla,
            )
            source_summary = _summarize_rows(source_rows)
            system_summary = _summarize_rows(system_rows)

        # Comparison logic (mostly for 'svod' tab)
        compare_enabled = len(snapshots) >= 2 and self.request.GET.get("compare") == "1"
        left_id = self.request.GET.get("left_snapshot_id")
        right_id = self.request.GET.get("right_snapshot_id")

        compare_rows = []
        compare_summary = None
        compare_left = None
        compare_right = None

        if len(snapshots) >= 2 and not left_id and not right_id:
            left_id = str(snapshots[1].id)
            right_id = str(snapshots[0].id)

        if compare_enabled and left_id and right_id:
            compare_left = FiveInitiativeApplicationSnapshot.objects.filter(pk=left_id).first()
            compare_right = FiveInitiativeApplicationSnapshot.objects.filter(pk=right_id).first()
            if compare_left and compare_right and compare_left.pk != compare_right.pk:
                left_entries = list(
                    FiveInitiativeApplicationEntry.objects.filter(snapshot=compare_left).select_related("mahalla")
                )
                right_entries = list(
                    FiveInitiativeApplicationEntry.objects.filter(snapshot=compare_right).select_related("mahalla")
                )
                left_rows = _aggregate_system_rows(left_entries)
                right_rows = _aggregate_system_rows(right_entries)
                compare_rows = _build_compare_rows(left_rows, right_rows)
                compare_summary = _build_compare_summary(compare_rows)

        # Build snapshot choice lists with selected flag (avoids complex template logic)
        snapshot_choices_left = [
            {
                "id": s.id,
                "label": f"{timezone.localtime(s.created_at).strftime('%d.%m.%Y %H:%M')} ({s.source_file_name[:20]})",
                "selected": str(s.id) == left_id,
            }
            for s in snapshots
        ]
        snapshot_choices_right = [
            {
                "id": s.id,
                "label": f"{timezone.localtime(s.created_at).strftime('%d.%m.%Y %H:%M')} ({s.source_file_name[:20]})",
                "selected": str(s.id) == right_id,
            }
            for s in snapshots
        ]

        context.update(
            {
                "active_tab": active_tab,
                "snapshots": snapshots,
                "snapshot": current_snapshot,
                "rows": system_rows,
                "source_rows": source_rows,
                "system_rows": system_rows,
                "method_diff_rows": method_diff_rows,
                "selected_left_snapshot_id": left_id,
                "selected_right_snapshot_id": right_id,
                "snapshot_choices_left": snapshot_choices_left,
                "snapshot_choices_right": snapshot_choices_right,
                "compare_enabled": compare_enabled,
                "compare_rows": compare_rows,
                "compare_summary": compare_summary,
                "compare_left": compare_left,
                "compare_right": compare_right,
                "can_upload": getattr(self.request.user, "is_site_admin", False),
                "meta_rows_total": (current_snapshot.display_meta or {}).get("rows_total", 0) if current_snapshot else 0,
                "meta_unique_pinfl": (current_snapshot.display_meta or {}).get("unique_pinfl", 0) if current_snapshot else 0,
                "meta_matched_pinfl": (current_snapshot.display_meta or {}).get("matched_pinfl", 0) if current_snapshot else 0,
                "meta_not_found_pinfl": (current_snapshot.display_meta or {}).get("not_found_pinfl", 0) if current_snapshot else 0,
                "source_applications_total": source_summary["applications_count"],
                "source_unique_total": source_summary["unique_participants_count"],
                "system_applications_total": system_summary["applications_count"],
                "system_unique_total": system_summary["unique_participants_count"],
                "method_delta_applications": system_summary["applications_count"] - source_summary["applications_count"],
                "method_delta_unique": system_summary["unique_participants_count"] - source_summary["unique_participants_count"],
            }
        )
        return context


class FiveInitiativeApplicationSvodView(FiveInitiativeApplicationSvodTabsView):
    """Old URL backward compatibility."""
    default_tab = "svod"


class FiveInitiativeYouthListView(LoginRequiredMixin, ListView):
    model = Yosh
    template_name = "beshtashabbus/application_tabs.html"
    context_object_name = "yoshlar"
    paginate_by = 50

    def get_queryset(self):
        user = self.request.user
        queryset = Yosh.objects.select_related("mahalla")
        
        # Filter by mahalla if not admin
        if not getattr(user, "is_site_admin", False) and user.mahalla:
            queryset = queryset.filter(mahalla=user.mahalla)
            
        # Search filter
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(Q(fullname__icontains=q) | Q(jshshir__icontains=q))
            
        # Mahalla filter
        mahalla_id = self.request.GET.get('mahalla')
        if mahalla_id:
            queryset = queryset.filter(mahalla_id=mahalla_id)

        # Snapshot for status filtering
        snapshots = list(FiveInitiativeApplicationSnapshot.objects.all()[:50])
        snapshot_id = self.request.GET.get('snapshot_id')
        current_snapshot = None
        if snapshot_id:
            try:
                current_snapshot = FiveInitiativeApplicationSnapshot.objects.filter(pk=snapshot_id).first()
            except (ValueError, TypeError):
                current_snapshot = None
        if not current_snapshot and snapshots:
            current_snapshot = snapshots[0]

        status_filter = self.request.GET.get("status")
        if status_filter in {"applied", "not_applied"} and current_snapshot:
            pinfls = FiveInitiativeApplicationEntry.objects.filter(
                snapshot=current_snapshot
            ).values_list("pinfl", flat=True).distinct()
            if status_filter == "applied":
                queryset = queryset.filter(jshshir__in=pinfls)
            else:
                queryset = queryset.exclude(jshshir__in=pinfls)
            
        return queryset.order_by('fullname')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        active_tab = "youth_list"
        
        # Snapshot selection
        snapshots = list(FiveInitiativeApplicationSnapshot.objects.all()[:50])
        for s in snapshots:
            s.display_meta = _resolve_snapshot_meta(s)
            
        snapshot_id = self.request.GET.get('snapshot_id')
        current_snapshot = None
        if snapshot_id:
            try:
                current_snapshot = FiveInitiativeApplicationSnapshot.objects.filter(pk=snapshot_id).first()
            except (ValueError, TypeError):
                pass
        if not current_snapshot and snapshots:
            current_snapshot = snapshots[0]
            
        context.update({
            "active_tab": active_tab,
            "snapshots": snapshots,
            "snapshot": current_snapshot,
            "can_upload": getattr(user, "is_site_admin", False),
            "can_submit_application": _can_submit_application(user),
        })
        
        # Get application data for current page's youth
        yoshlar = context['yoshlar']
        pinfls = [y.jshshir for y in yoshlar]
        
        if current_snapshot and pinfls:
            entries = FiveInitiativeApplicationEntry.objects.filter(
                snapshot=current_snapshot, 
                pinfl__in=pinfls
            )
            # Group by PINFL
            app_map = defaultdict(list)
            for entry in entries:
                app_map[entry.pinfl].append(entry.direction)
            
            # Attach to yoshlar
            for y in yoshlar:
                y.applied_directions = app_map.get(y.jshshir, [])
                y.app_count = len(y.applied_directions)
        else:
            for y in yoshlar:
                y.applied_directions = []
                y.app_count = 0

        today = timezone.localdate()
        for y in yoshlar:
            if y.birth_date:
                years = today.year - y.birth_date.year
                if (today.month, today.day) < (y.birth_date.month, y.birth_date.day):
                    years -= 1
                y.display_age = max(years, 0)
            else:
                y.display_age = None
                
        # For filters
        if getattr(user, "is_site_admin", False):
            context["mahallas"] = Mahalla.objects.all()
        else:
            context["mahallas"] = (
                Mahalla.objects.filter(id=user.mahalla.id) if user.mahalla else Mahalla.objects.none()
            )
            
        context["selected_mahalla"] = int(self.request.GET.get('mahalla')) if self.request.GET.get('mahalla') else None
        context["search_query"] = self.request.GET.get('q', '')
        context["selected_status"] = self.request.GET.get("status", "")
        context["sporttype_categories"] = SPORTTYPE_CATEGORY_CHOICES
        
        return context


class FiveInitiativeSportTypesView(LoginRequiredMixin, View):
    def get(self, request):
        if not _can_submit_application(request.user):
            return JsonResponse({"success": False, "error": "Ruxsat yo'q."}, status=403)
        try:
            yosh_id = int(request.GET.get("yosh_id", 0))
            category_id = int(request.GET.get("category_id", 0))
        except Exception:
            return JsonResponse({"success": False, "error": "Parametr noto'g'ri."}, status=400)

        if not yosh_id or not category_id:
            return JsonResponse({"success": False, "error": "Parametr yetarli emas."}, status=400)

        yosh = Yosh.objects.filter(pk=yosh_id).first()
        if not yosh:
            return JsonResponse({"success": False, "error": "Yosh topilmadi."}, status=404)

        user = request.user
        if not getattr(user, "is_site_admin", False) and user.mahalla_id != yosh.mahalla_id:
            return JsonResponse({"success": False, "error": "Ruxsat yo'q."}, status=403)

        if not yosh.birth_date:
            return JsonResponse({"success": False, "error": "Tug'ilgan sana bazada topilmadi."}, status=400)

        gender_id = _gender_id_from_pinfl(yosh.jshshir)
        if not gender_id:
            return JsonResponse({"success": False, "error": "PINFL bo'yicha gender aniqlanmadi."}, status=400)

        params = {
            "lang": "uz_latn",
            "dateOfBirth": yosh.birth_date.strftime("%d.%m.%Y"),
            "genderId": gender_id,
            "agecategoryid": 0,
            "sporttypecategoryid": category_id,
            "isSeasonDoc": "true",
            "initiativtypeid": 1,
            "isonlineregistration": "true",
            "healthtypeid": 1,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        try:
            response = _request_with_proxy_fallback(
                "GET",
                "https://api.5tashabbus.uz/SportType/GetAll",
                headers=headers,
                params=params,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            return JsonResponse({"success": False, "error": f"Internet xatoligi (SportType): {e}"}, status=502)
        except ValueError:
            return JsonResponse({"success": False, "error": "SportType javobi JSON emas"}, status=502)

        if not isinstance(data, list):
            return JsonResponse({"success": False, "error": "SportType javobi noto'g'ri formatda."}, status=502)

        return JsonResponse({"success": True, "items": data})


class FiveInitiativeApplicationSubmitView(LoginRequiredMixin, View):
    def post(self, request):
        error_prefix = "DBG20260323"
        if not _can_submit_application(request.user):
            return JsonResponse({"success": False, "error": f"{error_prefix}: Ruxsat yo'q."}, status=403)
        try:
            payload = request.POST
            yosh_id = int(payload.get("yosh_id"))
        except Exception:
            return JsonResponse({"success": False, "error": f"{error_prefix}: Yosh ID noto'g'ri."}, status=400)

        sporttype_id = payload.get("sporttype_id")
        sporttype_name = (payload.get("sporttype_name") or "").strip()
        category_id = payload.get("category_id")
        category_name = (payload.get("category_name") or "").strip()

        try:
            sporttype_id = int(sporttype_id)
            category_id = int(category_id)
        except Exception:
            return JsonResponse({"success": False, "error": f"{error_prefix}: Tanlov ma'lumoti noto'g'ri."}, status=400)

        if not sporttype_id or not sporttype_name:
            return JsonResponse({"success": False, "error": f"{error_prefix}: Yo'nalish tanlanmadi."}, status=400)
        if not category_id or not category_name:
            return JsonResponse({"success": False, "error": f"{error_prefix}: Kategoriya tanlanmadi."}, status=400)

        yosh = Yosh.objects.select_related("mahalla").filter(pk=yosh_id).first()
        if not yosh:
            return JsonResponse({"success": False, "error": f"{error_prefix}: Yosh topilmadi."}, status=404)

        user = request.user
        if not getattr(user, "is_site_admin", False) and user.mahalla_id != yosh.mahalla_id:
            return JsonResponse({"success": False, "error": f"{error_prefix}: Ruxsat yo'q."}, status=403)

        document_series, document_number, identity_document_id = _parse_identity_document(yosh)
        if not document_series or not document_number or not identity_document_id:
            return JsonResponse(
                {
                    "success": False,
                    "error": (
                        f"{error_prefix}: Pasport yoki guvohnoma seriya/raqami noto'g'ri. "
                        f"passport='{yosh.passport_number or ''}', "
                        f"guvohnoma='{yosh.guvohnoma_raqami or ''}'"
                    ),
                },
                status=400,
            )

        if not yosh.birth_date:
            return JsonResponse({"success": False, "error": f"{error_prefix}: Tug'ilgan sana bazada topilmadi."}, status=400)

        date_of_birth = yosh.birth_date.strftime("%d.%m.%Y")

        submitted_phone_number = request.POST.get("phone_number", "")
        phone_number = _format_phone_number(submitted_phone_number) or _format_phone_number(yosh.phone_number)
        if not phone_number:
            return JsonResponse({"success": False, "error": f"{error_prefix}: Telefon raqam formati noto'g'ri."}, status=400)
        session = requests.Session()
        request_id = uuid.uuid4().hex.upper()
        logger.info(
            "5tashabbus submit start request_id=%s yosh_id=%s identity_document_id=%s passport=%s guvohnoma=%s",
            request_id,
            yosh.id,
            identity_document_id,
            _mask_document(yosh.passport_number),
            _mask_document(yosh.guvohnoma_raqami),
        )
        last_error = "Captcha olinmadi."

        for attempt in range(1, DEFAULT_ATTEMPTS + 1):
            captcha_json, captcha_error = _get_captcha(phone_number, session=session, request_id=request_id)
            if captcha_error:
                last_error = captcha_error
            if not captcha_json:
                _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                continue

            captcha_b64 = captcha_json.get("captcha") or captcha_json.get("result")
            if not captcha_b64:
                last_error = f"Sayt xatoligi (captcha): captcha topilmadi: {captcha_json}"
                _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                continue

            try:
                captcha_text = _read_4_letters_from_png(captcha_b64)
            except Exception as exc:
                last_error = f"Captcha o'qishda xatolik: {exc}"
                _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                continue

            athlete_info, athlete_error = _get_athlete_info(
                captcha_text,
                document_series,
                document_number,
                date_of_birth,
                phone_number,
                identity_document_id,
                session=session,
                request_id=request_id,
            )
            if athlete_error:
                logger.warning("5tashabbus get_athlete_info transport error request_id=%s error=%s", request_id, athlete_error)
                last_error = athlete_error
            if not athlete_info:
                _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                continue

            if athlete_info.get("success") is not True:
                stage_error = _extract_message(athlete_info) or "GetAthleteInfo xatoligi."
                logger.warning(
                    "5tashabbus get_athlete_info reject request_id=%s response=%s",
                    request_id,
                    athlete_info,
                )
                last_error = f"GetAthleteInfo: {stage_error}"
                _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                continue

            athlete_result = athlete_info.get("result")
            if not isinstance(athlete_result, dict):
                last_error = "GetAthleteInfo natijasi noto'g'ri."
                _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                continue

            uploaded_photo_payload, attach_error = _attach_yosh_photo(
                yosh,
                session=session,
                identity_document_id=identity_document_id,
            )
            if attach_error:
                logger.warning("5tashabbus attach reject request_id=%s error=%s", request_id, attach_error)
                last_error = f"Attach: {attach_error}"
                _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)
                continue

            registration_payload = _build_registration_payload(
                athlete_result,
                document_series=document_series,
                document_number=document_number,
                identity_document_id=identity_document_id,
                sporttypeids=[sporttype_id],
                sporttypecategoryid=category_id,
                sporttypecategoryname=category_name,
                phonenumber=phone_number,
                photo_payload=uploaded_photo_payload,
            )

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Content-Type": "application/json",
            }
            try:
                insert_response = _request_with_proxy_fallback(
                    "POST",
                    INSERT_REGISTRATION_URL,
                    headers=headers,
                    json=registration_payload,
                    session=session,
                    timeout=20,
                )
                insert_result = insert_response.json()
            except requests.exceptions.RequestException as exc:
                logger.warning("5tashabbus insert transport error request_id=%s error=%s", request_id, exc)
                return JsonResponse({"success": False, "error": f"{error_prefix}: Internet xatoligi (InsertRegistration): {exc}"}, status=502)
            except ValueError:
                logger.warning("5tashabbus insert non-json request_id=%s", request_id)
                return JsonResponse({"success": False, "error": f"{error_prefix}: InsertRegistration javobi JSON emas"}, status=502)

            if insert_result and insert_result.get("success") is True:
                logger.info("5tashabbus insert success request_id=%s", request_id)
                return JsonResponse({"success": True, "message": "ok"})

            logger.warning(
                "5tashabbus insert reject request_id=%s response=%s payload_meta=%s",
                request_id,
                insert_result,
                {
                    "identity_document_id": identity_document_id,
                    "documentseries": document_series,
                    "documentnumber": _mask_document(document_number),
                    "sporttype_id": sporttype_id,
                    "category_id": category_id,
                    "photo_attachment": bool((registration_payload.get("photo") or {}).get("attachmentfileid")),
                },
            )
            last_error = f"InsertRegistration: {_extract_message(insert_result) or 'InsertRegistration xatoligi.'}"
            _wait_before_next_attempt(attempt, DEFAULT_ATTEMPTS)

        return JsonResponse({"success": False, "error": f"{error_prefix}: {last_error}"}, status=400)


class FiveInitiativeApplicationExtendedSvodView(FiveInitiativeApplicationSvodTabsView):
    """Old URL backward compatibility."""
    default_tab = "extended"


def _normalize_gender_for_match(raw_gender: str) -> str:
    """Normalize gender value to 'male' or 'female' or '' for matching."""
    g = (raw_gender or "").strip().lower()
    if "жен" in g or "female" in g or "ayol" in g:
        return "female"
    if "муж" in g or "male" in g or "erkak" in g:
        return "male"
    return ""


def _build_svod_norma_table(snapshot, mahalla_names):
    """Build the full svod norma table structured as in the Excel.

    Returns a list of row dicts:
    {
        'norm': FiveInitiativeSvodNorm,
        'cells': [{'value': int, 'norma': int, 'status': 'ok'|'low'}, ...],
        'total': int,
    }
    and total_row dict with per-column totals.
    """
    if not snapshot:
        return [], {}

    norms = list(FiveInitiativeSvodNorm.objects.all())
    if not norms:
        return [], {}

    # Load all entries for this snapshot once
    entries_qs = FiveInitiativeApplicationEntry.objects.filter(
        snapshot=snapshot,
    ).select_related('mahalla')
    entries = list(entries_qs)

    # Build PINFL -> mahalla_name mapping via Yosh table
    pinfls = {e.pinfl for e in entries if e.pinfl}
    pinfl_mahalla = {}
    if pinfls:
        for chunk in _chunked(pinfls):
            for yosh_obj in Yosh.objects.select_related('mahalla').filter(jshshir__in=chunk):
                if yosh_obj.mahalla_id:
                    pinfl_mahalla[yosh_obj.jshshir] = yosh_obj.mahalla.name

    # Precompute: for each (category, direction, age_category, mahalla_name) -> {'male': count, 'female': count, '': count}
    # We count entries grouped by these keys
    counter = defaultdict(lambda: defaultdict(int))
    for e in entries:
        m_name = pinfl_mahalla.get(e.pinfl)
        if not m_name:
            continue
        cat = (e.selection_category or "").strip()
        dirn = (e.direction or "").strip()
        age = (e.age_category or "").strip()
        gender = _normalize_gender_for_match(e.gender)

        # Always count by explicit gender
        key = (cat, dirn, age, m_name)
        counter[key][gender] += 1
        counter[key][""] += 1  # total regardless of gender

    # Build result table
    result_rows = []
    col_totals = [0] * len(mahalla_names)
    col_norma_statuses = [{'ok': 0, 'low': 0} for _ in mahalla_names]

    for norm in norms:
        cells = []
        row_total = 0
        for col_idx, m_name in enumerate(mahalla_names):
            key = (norm.selection_category, norm.direction, norm.age_category, m_name)
            bucket = counter.get(key, {})

            if norm.gender:
                # Only count the specified gender
                value = bucket.get(norm.gender, 0)
            else:
                # Count both: use the total
                value = bucket.get("", 0)

            status = 'ok' if value >= norm.norma else 'low'
            cells.append({
                'value': value,
                'norma': norm.norma,
                'status': status,
            })
            col_totals[col_idx] += value
            row_total += value

        result_rows.append({
            'norm': norm,
            'cells': cells,
            'total': row_total,
        })

    return result_rows, col_totals


class FiveInitiativeSvodNormaView(LoginRequiredMixin, TemplateView):
    """5 tashabbus svod norma jadvali sahifasi."""
    template_name = "beshtashabbus/application_tabs.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        snapshots = list(FiveInitiativeApplicationSnapshot.objects.all()[:50])
        for s in snapshots:
            s.display_meta = _resolve_snapshot_meta(s)

        # Snapshot tanlash
        snapshot_id = self.request.GET.get('snapshot_id')
        current_snapshot = None
        if snapshot_id:
            current_snapshot = FiveInitiativeApplicationSnapshot.objects.filter(pk=snapshot_id).first()
        if not current_snapshot and snapshots:
            current_snapshot = snapshots[0]

        # Mahalla ro'yxati – admin / rahbar uchun hammasi, oddiy user uchun faqat o'ziniki
        is_admin = getattr(user, 'is_site_admin', False)
        if is_admin:
            mahallas = list(Mahalla.objects.all())
        elif user.mahalla:
            mahallas = [user.mahalla]
        else:
            mahallas = []

        mahalla_names = [m.name for m in mahallas]

        svod_rows, col_totals = _build_svod_norma_table(current_snapshot, mahalla_names)

        context.update({
            'active_tab': 'svod_norma',
            'snapshots': snapshots,
            'snapshot': current_snapshot,
            'can_upload': is_admin,
            'can_submit_application': _can_submit_application(user),
            'svod_mahalla_names': mahalla_names,
            'svod_rows': svod_rows,
            'svod_col_totals': col_totals,
        })
        return context
