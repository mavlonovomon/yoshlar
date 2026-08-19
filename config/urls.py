from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('auth.urls')),
    path('ishsiz_yoshlar/', include('ishsiz_yoshlar.urls')),
    path('otaliq/', include('otaliq.urls')),
    path('migratsiya/', include('migratsiya.urls')),
    path('reyd/', include('reyd.urls')),
    path('beshtashabbus/', include('beshtashabbus.urls')),
    path('yoqlama/', include('yoqlama.urls')),
    path('profilaktika/', include('profilaktika.urls')),
    path('kredit-yonaltirish/', include('kredit_yo_naltirish.urls')),
    path('intizom-jazo/', include('intizom_jazo.urls')),
    path('bilim-sinovi/', include('bilim_sinovi.urls')),
    path('hisobot/', include('hisobot.urls')),
    path('sorovnoma/', include('sorovnoma.urls')),
    path('ekin-yerlari/', include('ekin_yerlari.urls')),
    path('eco-energiya/', include('eco_energiya.urls')),
    path('', include('core.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
