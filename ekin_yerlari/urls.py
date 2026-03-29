from django.urls import path

from . import views

app_name = "ekin_yerlari"

urlpatterns = [
    path("", views.EkinYerDashboardView.as_view(), name="index"),
    path("list/", views.EkinYerListView.as_view(), name="list"),
    path("map/", views.EkinYerMapView.as_view(), name="map"),
    path("map-data/", views.ekin_yer_map_data, name="map_data"),
    path("resolve/<int:pk>/", views.EkinYerResolveView.as_view(), name="resolve"),
    path("resolve/<int:pk>/assign/", views.ekin_yer_assign_yosh, name="assign"),
    path("import/", views.ekin_yer_import_from_file, name="import"),
]
