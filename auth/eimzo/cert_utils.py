from datetime import datetime


def extract_pinfl(cert_info: dict) -> str | None:
    """
    Sertifikatdan PINFL olish.
    Real loyihada PINFL odatda subject yoki extension ichida bo'ladi.
    cert_info - verifier qaytargan dict (placeholder).
    """
    return cert_info.get('pinfl')


def extract_cn(cert_info: dict) -> str | None:
    """Sertifikat egasining to'liq ismi (CN)."""
    return cert_info.get('cn')


def extract_validity(cert_info: dict) -> tuple[datetime | None, datetime | None]:
    """Sertifikat amal qilish muddatlari."""
    return cert_info.get('not_before'), cert_info.get('not_after')
