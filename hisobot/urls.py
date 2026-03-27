from django.urls import path

from .views import HisobotView

app_name = "hisobot"

urlpatterns = [
    path("", HisobotView.as_view(), name="index"),
]
