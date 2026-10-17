from django.urls import path

from . import views

app_name = "equipos"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nuevo/", views.crear, name="crear"),
    path("importar/", views.importar, name="importar"),
    path("importar/plantilla.xlsx", views.plantilla, name="plantilla"),
    path("<int:pk>/", views.ficha, name="ficha"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/estado/", views.cambiar_estado, name="estado"),
    path("<int:pk>/documentos/nuevo/", views.subir_documento, name="documento"),
    path("<int:pk>/etiqueta/", views.etiqueta, name="etiqueta"),
]
