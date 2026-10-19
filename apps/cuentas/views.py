from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from .forms import (ConfiguracionForm, IngresoForm, RestablecerContrasenaForm,
                    UsuarioCrearForm, UsuarioEditarForm)
from .models import Configuracion, Rol, Usuario
from .permisos import GESTORES, SOLO_ADMIN, GestoresMixin, rol_requerido


def usuarios_gestionables(gestor):
    """El Administrador maneja a todos; el Encargado, a los técnicos de las áreas de sus laboratorios."""
    if gestor.es_administrador:
        return Usuario.objects.all()
    return (Usuario.objects.filter(rol=Rol.TECNICO, areas__in=gestor.areas_permitidas())
            .exclude(pk=gestor.pk).distinct())


class ConEditorMixin:
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["editor"] = self.request.user
        return kwargs


class IngresoView(auth_views.LoginView):
    """RF-01: iniciar sesión con usuario y contraseña personales."""

    authentication_form = IngresoForm
    redirect_authenticated_user = True


class CambiarContrasenaView(SuccessMessageMixin, auth_views.PasswordChangeView):
    """RF-04: cada usuario cambia su propia contraseña."""

    success_url = reverse_lazy("core:inicio")
    success_message = "Tu contraseña se cambió correctamente."


class UsuarioListaView(GestoresMixin, ListView):
    model = Usuario
    template_name = "cuentas/usuario_lista.html"
    context_object_name = "usuarios"
    paginate_by = 25

    def get_queryset(self):
        qs = usuarios_gestionables(self.request.user).prefetch_related("areas__laboratorio", "laboratorios")
        self.q = self.request.GET.get("q", "").strip()
        self.rol = self.request.GET.get("rol", "")
        self.estado = self.request.GET.get("estado", "")
        if self.q:
            qs = qs.filter(Q(nombre__icontains=self.q) | Q(username__icontains=self.q) | Q(email__icontains=self.q))
        if self.rol in Rol.values:
            qs = qs.filter(rol=self.rol)
        if self.estado == "activos":
            qs = qs.filter(is_active=True)
        elif self.estado == "inactivos":
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(q=self.q, rol=self.rol, estado=self.estado,
                   roles=Rol.choices if self.request.user.es_administrador else None)
        return ctx


class UsuarioCrearView(GestoresMixin, ConEditorMixin, SuccessMessageMixin, CreateView):
    """RF-03: crear usuarios y asignarles un rol."""

    model = Usuario
    form_class = UsuarioCrearForm
    template_name = "cuentas/usuario_form.html"
    success_url = reverse_lazy("cuentas:usuarios")
    success_message = "Se creó el usuario %(nombre)s."


class UsuarioEditarView(GestoresMixin, ConEditorMixin, SuccessMessageMixin, UpdateView):
    """RF-03: modificar, cambiar el rol o desactivar un usuario."""

    model = Usuario
    form_class = UsuarioEditarForm
    template_name = "cuentas/usuario_form.html"
    success_url = reverse_lazy("cuentas:usuarios")
    success_message = "Se guardaron los cambios de %(nombre)s."

    def get_queryset(self):
        return usuarios_gestionables(self.request.user)


@rol_requerido(*GESTORES)
def restablecer_contrasena(request, pk):
    """RF-03: el administrador (o el encargado, a sus técnicos) restablece la contraseña de un usuario."""
    usuario = get_object_or_404(usuarios_gestionables(request.user), pk=pk)
    form = RestablecerContrasenaForm(usuario, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Se restableció la contraseña de {usuario}. Entrégasela de forma segura.")
        return redirect("cuentas:usuarios")
    return render(request, "cuentas/restablecer.html", {"form": form, "usuario": usuario})


@rol_requerido(*SOLO_ADMIN)
def configuracion(request):
    """RF-27: el administrador define el plazo de aviso y la hora del envío diario."""
    form = ConfiguracionForm(request.POST or None, instance=Configuracion.actual())
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Se guardó la configuración.")
        return redirect("cuentas:configuracion")
    return render(request, "cuentas/configuracion.html", {"form": form})
