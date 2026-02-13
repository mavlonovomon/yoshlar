from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model


User = get_user_model()


class EimzoBackend(BaseBackend):
    """
    E-IMZO autentifikatsiya backend.
    authenticate(..., pinfl=..., full_name=...) orqali ishlaydi.
    """
    def authenticate(self, request, pinfl=None, full_name=None, **kwargs):
        if not pinfl:
            return None

        user = User.objects.filter(pinfl=pinfl).first()
        if user is None:
            # Yangi foydalanuvchi yaratish
            username = pinfl
            user = User(username=username, full_name=full_name or pinfl, pinfl=pinfl)
            user.set_unusable_password()
            user.save()
        else:
            # F.I.Sh yangilash (agar kelgan bo'lsa)
            if full_name and user.full_name != full_name:
                user.full_name = full_name
                user.save(update_fields=['full_name'])

        return user

    def get_user(self, user_id):
        return User.objects.filter(pk=user_id).first()
