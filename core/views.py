from .views_auth import login_view, logout_view
from .views_yosh import (
    dashboard,
    info_view,
    meeting_edit,
    user_list,
    user_profile,
    yosh_detail,
    yosh_list,
)

__all__ = [
    "login_view",
    "logout_view",
    "dashboard",
    "yosh_list",
    "yosh_detail",
    "meeting_edit",
    "info_view",
    "user_profile",
    "user_list",
]
