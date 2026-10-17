from django.urls import path

from . import views

app_name = "catalogos"

urlpatterns = [
    path("", views.indice, name="indice"),
    path("<slug:clave>/", views.lista, name="lista"),
    path("<slug:clave>/nuevo/", views.editar, name="crear"),
    path("<slug:clave>/<int:pk>/", views.editar, name="editar"),
]
