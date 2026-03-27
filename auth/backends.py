from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model


User = get_user_model()


class EimzoBackend(BaseBackend):
    """
    E-IMZO autentifikatsiya backend.
    authenticate(..., pinfl=..., full_name=...) orqali ishlaydi.
    Faqat bazada mavjud PINFL foydalanuvchini autentifikatsiya qiladi.
    """

    def authenticate(self, request, pinfl=None, full_name=None, **kwargs):
        if not pinfl:
            return None

        pinfl_norm = ''.join(ch for ch in str(pinfl) if ch.isdigit())
        if len(pinfl_norm) != 14:
            return None

        user = User.objects.filter(pinfl=pinfl_norm).first()
        if user is None:
            return None
        return user

    def get_user(self, user_id):
        return User.objects.filter(pk=user_id).first()
