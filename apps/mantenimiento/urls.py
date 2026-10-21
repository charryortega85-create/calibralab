from django.urls import path

from . import views

app_name = "mantenimiento"

urlpatterns = [
    path("", views.indice, name="indice"),
    path("equipos/<int:equipo_pk>/novedad/", views.novedad_editar, name="novedad_crear"),
    path("novedades/<int:pk>/", views.novedad_editar, name="novedad_editar"),
    path("equipos/<int:equipo_pk>/plan/", views.plan_editar, name="plan_crear"),
    path("planes/<int:pk>/", views.plan_editar, name="plan_editar"),
    path("evaluaciones/<int:servicio_pk>/", views.evaluacion, name="evaluacion"),
]
