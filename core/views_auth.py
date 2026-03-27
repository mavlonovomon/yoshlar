from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render

from .forms import MahallaLoginForm
from .models import User


def login_view(request):
    if request.method == "POST":
        form = MahallaLoginForm(request.POST)
        if form.is_valid():
            mahalla = form.cleaned_data.get("mahalla")
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")

            if mahalla:
                user = User.objects.filter(mahalla=mahalla, role="YETAKCHI").first()
                if user and user.check_password(password):
                    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                    return redirect("dashboard")
                form.add_error(None, "Ushbu mahalla yetakchisi topilmadi yoki parol noto'g'ri")
            elif username:
                user = authenticate(request, username=username, password=password)
                if user:
                    login(request, user)
                    return redirect("dashboard")
                form.add_error(None, "Login yoki parol noto'g'ri")
            else:
                form.add_error(None, "Mahalla tanlang yoki Admin login kiriting")
    else:
        form = MahallaLoginForm()

    return render(request, "login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("login")


import requests
from django.conf import settings
import urllib.parse

def login_oneid(request):
    """OneID sahifasiga yo'naltirish"""
    client_id = getattr(settings, 'ONEID_CLIENT_ID', '')
    redirect_uri = getattr(settings, 'ONEID_REDIRECT_URI', '')
    auth_url = getattr(settings, 'ONEID_AUTH_URL', 'https://sso.egov.uz/sso/oauth/Authorization.do')
    
    params = {
        'response_type': 'one_code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': 'egov',
        'state': 'random_state_string' # CSRF uchun yaxshilash mumkin
    }
    url = f"{auth_url}?{urllib.parse.urlencode(params)}"
    return redirect(url)


def callback_oneid(request):
    """OneID dan qaytgan kodni qabul qilib, tokenga va ma'lumotga almashtirish"""
    code = request.GET.get('code')
    if not code:
        return render(request, "login.html", {"form": MahallaLoginForm(), "oneid_error": "OneID dan kod qaytmadi."})

    client_id = getattr(settings, 'ONEID_CLIENT_ID', '')
    client_secret = getattr(settings, 'ONEID_CLIENT_SECRET', '')
    redirect_uri = getattr(settings, 'ONEID_REDIRECT_URI', '')
    token_url = getattr(settings, 'ONEID_TOKEN_URL', 'https://sso.egov.uz/sso/oauth/Authorization.do')

    # Token olish
    data = {
        'grant_type': 'one_authorization_code',
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'code': code,
    }

    try:
        response = requests.post(token_url, data=data)
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('access_token')
            
            if access_token:
                # Odatda OneID access_token bilan birga user_id, pinfl va boshqa parametrlarni qaytaradi.
                # Yoki alohida user_info URL ga so'rov tashlash kerak bo'ladi.
                # (Oddiy sso.egov.uz da pinfl token response ichida bo'ladi)
                pinfl = token_data.get('pinfl')
                
                if pinfl:
                    user = User.objects.filter(pinfl=pinfl).first()
                    if user:
                        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                        return redirect("dashboard")
                    else:
                        return render(request, "login.html", {
                            "form": MahallaLoginForm(), 
                            "oneid_error": "Siz tizimga kiritilmagansiz, ma'muriyatga murojaat qiling."
                        })
                else:
                    return render(request, "login.html", {"form": MahallaLoginForm(), "oneid_error": "OneID tizimidan PINFL qabul qilinmadi."})
            
    except Exception as e:
        return render(request, "login.html", {"form": MahallaLoginForm(), "oneid_error": f"OneID bilan ulanishda xatolik: {e}"})

    return render(request, "login.html", {"form": MahallaLoginForm(), "oneid_error": "OneID avtorizatsiyasi muvaffaqiyatsiz tugadi."})
