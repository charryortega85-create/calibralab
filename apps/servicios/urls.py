from django.urls import path

from . import views

app_name = "servicios"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nuevo/", views.crear, name="crear"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/corregir/", views.corregir, name="corregir"),
    path("<int:pk>/decision/", views.decision, name="decision"),
]
