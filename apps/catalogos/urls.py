from django.urls import path

from . import laboratorios, views

app_name = "catalogos"

urlpatterns = [
    path("", views.indice, name="indice"),
    path("laboratorios/", laboratorios.indice, name="laboratorios"),
    path("laboratorios/nuevo/", laboratorios.laboratorio_editar, name="laboratorio_crear"),
    path("laboratorios/<int:pk>/", laboratorios.laboratorio_editar, name="laboratorio_editar"),
    path("areas/nueva/", laboratorios.area_editar, name="area_crear"),
    path("areas/<int:pk>/", laboratorios.area_editar, name="area_editar"),
    path("<slug:clave>/", views.lista, name="lista"),
    path("<slug:clave>/nuevo/", views.editar, name="crear"),
    path("<slug:clave>/<int:pk>/", views.editar, name="editar"),
]
