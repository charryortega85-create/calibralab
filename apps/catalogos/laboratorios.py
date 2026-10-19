"""
Laboratorios y sus áreas. El Administrador crea laboratorios y áreas de cualquiera; el Encargado
de laboratorio ve solo los suyos y les agrega o corrige áreas.
"""
from django import forms
from django.contrib import messages
from django.db.models import Count, Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.cuentas.models import Rol
from apps.cuentas.permisos import GESTORES, SOLO_ADMIN, rol_requerido

from .models import Area, Laboratorio


def laboratorios_de(usuario):
    return Laboratorio.objects.all() if usuario.es_administrador else usuario.laboratorios.all()


@rol_requerido(*GESTORES)
def indice(request):
    areas = Area.objects.annotate(n_equipos=Count("equipos", distinct=True)).order_by("-activo", "nombre")
    labs = (laboratorios_de(request.user).order_by("-activo", "nombre")
            .prefetch_related(Prefetch("areas", queryset=areas),
                              Prefetch("encargados", queryset=_activos(Rol.ENCARGADO))))
    return render(request, "catalogos/laboratorios.html", {"labs": labs})


def _activos(rol):
    from apps.cuentas.models import Usuario

    return Usuario.objects.filter(rol=rol, is_active=True).order_by("nombre")


class LaboratorioForm(forms.ModelForm):
    class Meta:
        model = Laboratorio
        fields = ["nombre", "activo"]


class AreaForm(forms.ModelForm):
    class Meta:
        model = Area
        fields = ["laboratorio", "nombre", "activo"]

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["laboratorio"].queryset = laboratorios_de(usuario)
        if len(self.fields["laboratorio"].queryset) == 1:
            self.fields["laboratorio"].initial = self.fields["laboratorio"].queryset[0]


def _form(request, form, titulo):
    return render(request, "core/form.html", {
        "form": form, "titulo": titulo,
        "migas": [("Laboratorios y áreas", reverse("catalogos:laboratorios"))],
        "volver": reverse("catalogos:laboratorios"),
    })


@rol_requerido(*SOLO_ADMIN)
def laboratorio_editar(request, pk=None):
    obj = get_object_or_404(Laboratorio, pk=pk) if pk else None
    form = LaboratorioForm(request.POST or None, instance=obj)
    if obj is None:
        form.fields.pop("activo")
    if request.method == "POST" and form.is_valid():
        lab = form.save()
        messages.success(request, f"Se guardó el laboratorio «{lab}».")
        return redirect("catalogos:laboratorios")
    return _form(request, form, f"Editar {obj}" if obj else "Nuevo laboratorio")


@rol_requerido(*GESTORES)
def area_editar(request, pk=None):
    obj = None
    if pk:
        obj = get_object_or_404(Area, pk=pk)
        if not laboratorios_de(request.user).filter(pk=obj.laboratorio_id).exists():
            raise Http404
    form = AreaForm(request.POST or None, instance=obj, usuario=request.user,
                    initial={"laboratorio": request.GET.get("laboratorio")} if obj is None else None)
    if obj is None:
        form.fields.pop("activo")
    if not form.fields["laboratorio"].queryset.exists():
        messages.error(request, "Todavía no tienes un laboratorio a cargo. Pide al administrador que te asigne uno.")
        return redirect("catalogos:laboratorios")
    if request.method == "POST" and form.is_valid():
        area = form.save()
        messages.success(request, f"Se guardó el área «{area.nombre}» en {area.laboratorio}.")
        return redirect("catalogos:laboratorios")
    return _form(request, form, f"Editar el área {obj.nombre}" if obj else "Nueva área")
