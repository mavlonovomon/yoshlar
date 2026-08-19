from django.urls import path

from . import views

app_name = "eco_energiya"

urlpatterns = [
    path("", views.EcoEnergiyaListView.as_view(), name="list"),
    path("<int:pk>/update/", views.solar_panel_update, name="update"),
]
