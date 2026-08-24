"""PFX (PKCS#12) kalit fayllarini yuklash va validatsiya."""
from __future__ import annotations

import base64
import binascii

from cryptography.hazmat.primitives.serialization import pkcs12

MAX_PFX_DECODED_SIZE_BYTES = 100 * 1024

ERR_WRONG_PASSWORD = "Parol xato yoki kalit buzilgan"


def decode_pfx(pfx_b64: str) -> tuple[bytes | None, str | None]:
    raw = (pfx_b64 or "").strip()
    if not raw:
        return None, "Kalit fayli yuborilmadi"
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        return None, "Kalit fayli base64 formatida emas"
    if not data or len(data) > MAX_PFX_DECODED_SIZE_BYTES:
        return None, "Fayl hajmi juda katta yoki bo'sh"
    return data, None


def load_pfx(pfx_b64: str, password: str):
    """
    Base64 PFX -> (private_key, certificate, error).
    Muvaffaqiyatda error=None, aks holda key/cert=None.
    """
    data, err = decode_pfx(pfx_b64)
    if err:
        return None, None, err

    try:
        key, cert, _extra = pkcs12.load_key_and_certificates(
            data, (password or "").encode("utf-8")
        )
    except (ValueError, TypeError):
        return None, None, ERR_WRONG_PASSWORD

    if key is None or cert is None:
        return None, None, "Kalit faylida shaxsiy kalit yoki sertifikat topilmadi"

    return key, cert, None
