import base64
import json
import uuid
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.core.cache import cache
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST, require_GET

from .eimzo.cms_signer import sign_nonce
from .eimzo.pkcs12 import load_pfx
from .eimzo.verifier import verify_cms_signature, verify_signature
from .eimzo.cert_utils import extract_pinfl, extract_validity


NONCE_TTL_SECONDS = getattr(settings, 'EIMZO_NONCE_TTL_SECONDS', 120)

EIMZO_PFX_MAX_B64_LEN = ((100 * 1024) // 3 + 1) * 4
EIMZO_RATE_LIMIT_ATTEMPTS = 5
EIMZO_RATE_LIMIT_WINDOW_SECONDS = 60
EIMZO_RATE_LIMIT_ERROR = "Juda ko'p urinish. Bir daqiqa kutib turing"


def _pfx_rate_limit_ok(request) -> bool:
    ident = request.session.session_key or request.META.get("REMOTE_ADDR", "anon")
    key = f"eimzo_pfx_attempts:{ident}"
    try:
        count = cache.incr(key)
    except ValueError:
        cache.add(key, 1, EIMZO_RATE_LIMIT_WINDOW_SECONDS)
        count = 1
    return count <= EIMZO_RATE_LIMIT_ATTEMPTS


def _verify_with_server_signing(request, nonce: str, pfx_b64: str, password: str):
    """
    PFX faylni qabul qilib, nonce ni serverda imzolaydi va qat'iy tekshiradi.
    Qaytadi: (is_valid, cert_info, error)
    """
    if not pfx_b64 or len(pfx_b64) > EIMZO_PFX_MAX_B64_LEN:
        return False, {}, "Fayl hajmi juda katta yoki bo'sh"

    if not _pfx_rate_limit_ok(request):
        return False, {}, EIMZO_RATE_LIMIT_ERROR

    key_obj, cert_obj, load_err = load_pfx(pfx_b64, password)
    if load_err:
        return False, {}, load_err

    try:
        cms_der = sign_nonce(nonce.encode("utf-8"), key_obj, cert_obj)
    except TypeError:
        return False, {}, "Kalit turi qo'llab-quvvatlanmaydi"
    except Exception:
        return False, {}, "Kalitni ishlatishda xatolik"

    cms_b64 = base64.b64encode(cms_der).decode("ascii")
    return verify_cms_signature(cms_b64, nonce)


@require_GET
def eimzo_login_page(request):
    return render(request, 'auth/eimzo_login.html')


@require_GET
@csrf_protect
def eimzo_challenge(request):
    nonce = uuid.uuid4().hex
    request.session['eimzo_nonce'] = nonce
    request.session['eimzo_nonce_ts'] = timezone.now().timestamp()
    request.session['eimzo_nonce_used'] = False
    return JsonResponse({'nonce': nonce})


@require_POST
@csrf_protect
def eimzo_verify(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Noto'g'ri JSON")

    signature = payload.get('signature')
    pfx_b64 = payload.get('pfx_b64')
    password = payload.get('password')
    cert = payload.get('cert')
    chain = payload.get('chain')
    cert_meta = payload.get('cert_meta')
    if not signature and not pfx_b64:
        return HttpResponseBadRequest("Imzo yuborilmadi")

    nonce = request.session.get('eimzo_nonce')
    nonce_ts = request.session.get('eimzo_nonce_ts')
    nonce_used = request.session.get('eimzo_nonce_used')

    if not nonce or not nonce_ts:
        return JsonResponse({'ok': False, 'error': 'Nonce topilmadi'}, status=400)

    if nonce_used:
        return JsonResponse({'ok': False, 'error': 'Nonce allaqachon ishlatilgan'}, status=400)

    age = timezone.now().timestamp() - float(nonce_ts)
    if age > NONCE_TTL_SECONDS:
        return JsonResponse({'ok': False, 'error': 'Nonce muddati tugagan'}, status=400)

    if pfx_b64:
        is_valid, cert_info, error = _verify_with_server_signing(
            request, nonce, pfx_b64, password or ""
        )
        if not is_valid and error == EIMZO_RATE_LIMIT_ERROR:
            return JsonResponse({'ok': False, 'error': error}, status=429)
    else:
        ca_bundle_path = getattr(settings, 'EIMZO_CA_BUNDLE_PATH', None)
        is_valid, cert_info, error = verify_signature(
            nonce,
            signature,
            cert_b64=cert,
            chain_b64=chain,
            ca_bundle_path=ca_bundle_path,
            cert_meta=cert_meta,
        )
    if not is_valid:
        return JsonResponse({'ok': False, 'error': error or "Imzo noto'g'ri"}, status=401)

    pinfl = extract_pinfl(cert_info)
    not_before, not_after = extract_validity(cert_info)

    if not pinfl:
        return JsonResponse({'ok': False, 'error': 'PINFL topilmadi'}, status=400)

    # Sertifikat muddati tekshiruvi
    now = timezone.now()
    if not_after and now > not_after:
        return JsonResponse({'ok': False, 'error': 'Sertifikat muddati tugagan'}, status=401)
    if not_before and now < not_before:
        return JsonResponse({'ok': False, 'error': 'Sertifikat hali kuchga kirmagan'}, status=401)

    user = authenticate(request, pinfl=pinfl)
    if user is None:
        return JsonResponse({'ok': False, 'error': "PINFL bo'yicha foydalanuvchi topilmadi"}, status=401)

    login(request, user)

    # nonce replay prevention
    request.session['eimzo_nonce_used'] = True
    messages.success(request, "E-IMZO orqali tizimga kirildi.")
    return JsonResponse({'ok': True, 'redirect': '/'})
