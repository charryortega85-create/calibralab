from django.urls import path

from . import views

app_name = "alertas"

urlpatterns = [
    path("", views.estado, name="estado"),
    path("avisos/", views.avisos, name="avisos"),
    path("avisos/enviar/", views.enviar_ahora, name="enviar"),
    path("avisos/<int:pk>/", views.aviso, name="aviso"),
]
