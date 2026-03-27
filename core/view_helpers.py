def is_management_user(user):
    return bool(
        user
        and (user.is_superuser or user.is_staff or getattr(user, "role", None) in {"SUPER_ADMIN", "RAHBAR"})
    )
