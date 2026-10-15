from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("apps.core.urls")),
    path("cuentas/", include("apps.cuentas.urls")),
    path("registro-de-cambios/", include("apps.auditoria.urls")),
    path("admin/", admin.site.urls),
]

handler403 = "apps.core.views.acceso_denegado"
handler404 = "apps.core.views.no_encontrado"

admin.site.site_header = "CalibraLab · Administración técnica"
admin.site.site_title = "CalibraLab"
