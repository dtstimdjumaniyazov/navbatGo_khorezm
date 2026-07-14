from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.views import OfertaView, PrivacyPolicyView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path("legal/privacy/", PrivacyPolicyView.as_view(), name="legal-privacy"),
    path("legal/privacy/uz/", PrivacyPolicyView.as_view(), {"lang": "uz"}, name="legal-privacy-uz"),
    path("legal/oferta/", OfertaView.as_view(), name="legal-oferta"),
    path("legal/oferta/uz/", OfertaView.as_view(), {"lang": "uz"}, name="legal-oferta-uz"),
]

if settings.DEBUG:
    # Отдача загруженных фото дев-сервером; в проде — nginx/whitenoise
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
