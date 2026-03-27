import time
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect, resolve_url


class IdleSessionMiddleware:
    """Expire authenticated sessions after configured inactivity period."""

    SESSION_KEY = '_last_activity_ts'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self._process_request(request)
        if response is not None:
            return response
        return self.get_response(request)

    def _process_request(self, request):
        user = getattr(request, 'user', None)
        if not getattr(user, 'is_authenticated', False):
            return None

        timeout_seconds = int(
            getattr(
                settings,
                'SESSION_IDLE_TIMEOUT',
                getattr(settings, 'SESSION_COOKIE_AGE', 1800),
            )
        )
        if timeout_seconds <= 0:
            return None

        now_ts = int(time.time())
        last_ts_raw = request.session.get(self.SESSION_KEY)

        if last_ts_raw is not None:
            try:
                last_ts = int(last_ts_raw)
            except (TypeError, ValueError):
                last_ts = now_ts

            if now_ts - last_ts > timeout_seconds:
                logout(request)
                if self._is_api_request(request):
                    return JsonResponse(
                        {
                            'ok': False,
                            'error': "Sessiya muddati tugagan. Qayta login qiling.",
                        },
                        status=401,
                    )

                login_url = resolve_url(getattr(settings, 'LOGIN_URL', 'login'))
                query = urlencode({'next': request.get_full_path(), 'expired': '1'})
                return redirect(f"{login_url}?{query}")

        request.session[self.SESSION_KEY] = now_ts
        return None

    @staticmethod
    def _is_api_request(request):
        accept = (request.headers.get('Accept') or '').lower()
        xrw = (request.headers.get('X-Requested-With') or '').lower()
        return 'application/json' in accept or xrw == 'xmlhttprequest'
