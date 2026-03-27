"""
E-IMZO imzosini tekshirish.
Bu modul CMS (PKCS#7) imzolarini tekshiradi.
"""
from __future__ import annotations

import base64
import re
import sys
from typing import Tuple

x509 = None
pkcs7 = None


def _ensure_cryptography() -> tuple[bool, str | None]:
    global x509, pkcs7
    if x509 is not None and pkcs7 is not None:
        return True, None
    try:
        from cryptography import x509 as _x509
        from cryptography.hazmat.primitives.serialization import pkcs7 as _pkcs7
        x509 = _x509
        pkcs7 = _pkcs7
        return True, None
    except Exception as exc:
        return False, str(exc)


def _extract_from_subject_str(subject: str) -> dict:
    info: dict[str, str] = {}
    if not subject:
        return info

    m = re.search(r"CN\s*=\s*([^,]+)", subject, flags=re.IGNORECASE)
    if m:
        info["cn"] = m.group(1).strip()

    m = re.search(r"(serialNumber|SERIALNUMBER|UID|PINFL|1\.2\.860\.3\.16\.1\.1)\s*=\s*([^,]+)", subject)
    if m:
        val = m.group(2).strip()
        if re.match(r"^\d{14}$", val):
            info["pinfl"] = val

    if "pinfl" not in info:
        m = re.search(r"\b\d{14}\b", subject)
        if m:
            info["pinfl"] = m.group(0)

    return info


def _extract_from_meta(cert_meta: dict | None) -> dict:
    meta = cert_meta if isinstance(cert_meta, dict) else {}

    info = {
        "subject": (meta.get("subject") or "").strip(),
        "serial": (meta.get("serial") or "").strip(),
        "cn": (meta.get("cn") or meta.get("full_name") or "").strip(),
        "pinfl": (meta.get("pinfl") or "").strip(),
        "not_before": None,
        "not_after": None,
    }

    if not info["pinfl"]:
        for key in ("subject", "serial", "cn"):
            text = info.get(key) or ""
            m = re.search(r"\b\d{14}\b", text)
            if m:
                info["pinfl"] = m.group(0)
                break

    if (not info["cn"]) and info["subject"]:
        info.update(_extract_from_subject_str(info["subject"]))

    return info


def _load_x509_from_maybe_base64(cert_value: str | None):
    if not cert_value:
        return None

    raw = cert_value.strip()
    if not raw:
        return None

    if "BEGIN CERTIFICATE" in raw:
        try:
            return x509.load_pem_x509_certificate(raw.encode("utf-8"))
        except Exception:
            return None

    try:
        der_data = base64.b64decode(raw)
        return x509.load_der_x509_certificate(der_data)
    except Exception:
        return None


def verify_signature(
    nonce: str,
    signature_b64: str,
    cert_b64: str | None = None,
    chain_b64: str | list[str] | None = None,
    ca_bundle_path: str | None = None,
    cert_meta: dict | None = None,
) -> Tuple[bool, dict, str | None]:
    """
    nonce va signature ni tekshiradi.
    Qaytadi: (is_valid, cert_info, error)
    """
    has_crypto, import_error = _ensure_cryptography()
    if not has_crypto:
        return (
            False,
            {},
            f"cryptography kutubxonasi topilmadi ({import_error}). "
            f"Interpreter: {sys.executable}",
        )

    try:
        if not isinstance(signature_b64, str):
            return False, {}, "Imzo formati noto'g'ri"

        sig_raw = (signature_b64 or "").strip()
        if not sig_raw:
            return False, {}, "Imzo bo'sh"

        if "BEGIN PKCS7" in sig_raw:
            sig_data = sig_raw.encode("utf-8")
        else:
            try:
                sig_data = base64.b64decode(sig_raw)
            except Exception:
                return False, {}, "Imzo base64 formatida emas"

        try:
            p7 = pkcs7.load_der_pkcs7_certificates(sig_data)
        except Exception:
            try:
                p7 = pkcs7.load_pem_pkcs7_certificates(sig_data)
            except Exception:
                return False, {}, "Imzo formati noto'g'ri (DER yoki PEM emas)"

        cert = p7[0] if p7 else None

        if cert is None:
            cert = _load_x509_from_maybe_base64(cert_b64)

        if cert is None and isinstance(chain_b64, list):
            for item in chain_b64:
                cert = _load_x509_from_maybe_base64(item)
                if cert is not None:
                    break
        elif cert is None and isinstance(chain_b64, str):
            cert = _load_x509_from_maybe_base64(chain_b64)

        if cert is None:
            return False, {}, "Imzo ichidan ham, cert/chain dan ham sertifikat topilmadi"

        cert_info = {
            "subject": cert.subject.rfc4514_string(),
            "serial": hex(cert.serial_number),
            "not_before": cert.not_valid_before_utc,
            "not_after": cert.not_valid_after_utc,
        }

        extracted = _extract_from_subject_str(cert_info["subject"])
        cert_info.update(extracted)

        if "pinfl" not in cert_info:
            fallback_info = _extract_from_meta(cert_meta)
            if fallback_info.get("pinfl"):
                cert_info.update({k: v for k, v in fallback_info.items() if v})
            else:
                return False, cert_info, "Sertifikatdan PINFL aniqlanmadi"

        return True, cert_info, None

    except Exception as e:
        return False, {}, f"Tekshirishda xatolik: {str(e)}"
