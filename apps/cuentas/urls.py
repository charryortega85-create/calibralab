from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "cuentas"

urlpatterns = [
    path("ingresar/", views.IngresoView.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("contrasena/", views.CambiarContrasenaView.as_view(), name="cambiar_contrasena"),
    path("usuarios/", views.UsuarioListaView.as_view(), name="usuarios"),
    path("usuarios/nuevo/", views.UsuarioCrearView.as_view(), name="usuario_crear"),
    path("usuarios/<int:pk>/", views.UsuarioEditarView.as_view(), name="usuario_editar"),
    path("usuarios/<int:pk>/contrasena/", views.restablecer_contrasena, name="usuario_contrasena"),
    path("configuracion/", views.configuracion, name="configuracion"),
]
