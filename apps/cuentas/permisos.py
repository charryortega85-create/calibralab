"""
Permisos por rol (RF-02, RNF-03).

Se comprueban en el servidor en cada vista, así que escribir a mano la dirección de
una pantalla que no corresponde al rol devuelve «acceso denegado» (403).
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from .models import Rol

EDITORES = (Rol.TECNICO, Rol.ENCARGADO, Rol.ADMINISTRADOR)
SOLO_ADMIN = (Rol.ADMINISTRADOR,)
# Laboratorios, áreas y usuarios: el Encargado solo los de sus laboratorios.
GESTORES = (Rol.ADMINISTRADOR, Rol.ENCARGADO)


def rol_requerido(*roles):
    def decorador(vista):
        @login_required
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if request.user.rol not in roles:
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador


class RolRequeridoMixin(LoginRequiredMixin):
    roles_permitidos = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.rol not in self.roles_permitidos:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class SoloAdministradorMixin(RolRequeridoMixin):
    roles_permitidos = SOLO_ADMIN


class GestoresMixin(RolRequeridoMixin):
    roles_permitidos = GESTORES


class EditoresMixin(RolRequeridoMixin):
    roles_permitidos = EDITORES
