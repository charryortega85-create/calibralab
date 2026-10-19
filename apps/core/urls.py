from django.urls import path

from . import publico, views

app_name = "core"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("archivos/<path:ruta>", views.archivo, name="archivo"),
    # Consulta pública al escanear un QR (sin iniciar sesión)
    path("qr/equipo/<str:token>/", publico.qr_equipo, name="qr_equipo"),
    path("qr/certificado/<str:token>/", publico.qr_certificado, name="qr_certificado"),
    path("qr/certificado/<str:token>/hoja/<int:n>/<int:p>/", publico.qr_hoja, name="qr_hoja"),
]
