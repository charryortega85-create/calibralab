from django.urls import path

from . import views

app_name = "reportes"

urlpatterns = [
    path("", views.indice, name="indice"),
    path("hoja-de-vida/<int:pk>/", views.hoja_vida, name="hoja_vida"),
    path("estado/", views.estado, name="estado"),
    path("vencimientos/", views.vencimientos, name="vencimientos"),
    path("ejecucion/", views.ejecucion, name="ejecucion"),
]
