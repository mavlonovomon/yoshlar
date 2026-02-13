import json
import uuid
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST, require_GET

from .eimzo.verifier import verify_signature
from .eimzo.cert_utils import extract_pinfl, extract_cn, extract_validity
from .models import EimzoProfile


NONCE_TTL_SECONDS = getattr(settings, 'EIMZO_NONCE_TTL_SECONDS', 120)


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
    cert = payload.get('cert')
    chain = payload.get('chain')
    if not signature:
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

    ca_bundle_path = getattr(settings, 'EIMZO_CA_BUNDLE_PATH', None)
    is_valid, cert_info, error = verify_signature(
        nonce,
        signature,
        cert_b64=cert,
        chain_b64=chain,
        ca_bundle_path=ca_bundle_path,
    )
    if not is_valid:
        return JsonResponse({'ok': False, 'error': error or "Imzo noto'g'ri"}, status=401)

    pinfl = extract_pinfl(cert_info)
    full_name = extract_cn(cert_info)
    not_before, not_after = extract_validity(cert_info)

    if not pinfl:
        return JsonResponse({'ok': False, 'error': 'PINFL topilmadi'}, status=400)

    # Sertifikat muddati tekshiruvi
    now = timezone.now()
    if not_after and now > not_after:
        return JsonResponse({'ok': False, 'error': 'Sertifikat muddati tugagan'}, status=401)
    if not_before and now < not_before:
        return JsonResponse({'ok': False, 'error': 'Sertifikat hali kuchga kirmagan'}, status=401)

    user = authenticate(request, pinfl=pinfl, full_name=full_name)
    if user is None:
        return JsonResponse({'ok': False, 'error': 'Autentifikatsiya xatoligi'}, status=401)

    login(request, user)

    # nonce replay prevention
    request.session['eimzo_nonce_used'] = True

    # Sertifikat profilini yangilash
    profile, _ = EimzoProfile.objects.get_or_create(user=user)
    profile.cert_serial = cert_info.get('serial')
    profile.cert_subject = cert_info.get('subject')
    profile.cert_valid_from = not_before
    profile.cert_valid_to = not_after
    profile.last_verified_at = now
    profile.save()

    messages.success(request, "E-IMZO orqali tizimga kirildi.")
    return JsonResponse({'ok': True, 'redirect': '/'})
