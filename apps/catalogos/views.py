"""RF-08: listas controladas. Todos las usan; solo el Administrador las modifica."""
from django import forms
from django.contrib import messages
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.cuentas.permisos import SOLO_ADMIN, rol_requerido

from .models import Marca, Proveedor, TipoInstrumento, Ubicacion, Unidad

# Los laboratorios y sus áreas tienen su propia página (ver laboratorios.py).
LISTAS = {
    "marcas": (Marca, ["nombre", "activo"]),
    "ubicaciones": (Ubicacion, ["nombre", "activo"]),
    "unidades": (Unidad, ["simbolo", "nombre", "magnitud", "activo"]),
    "proveedores": (Proveedor, ["nombre", "ruc", "contacto", "correo", "telefono", "reconocimiento", "acreditacion",
                                "acreditacion_vence", "activo"]),
    "tipos-de-instrumento": (TipoInstrumento, ["familia", "nombre", "activo"]),
}


def _lista(clave):
    if clave not in LISTAS:
        raise Http404
    return LISTAS[clave]


@rol_requerido(*SOLO_ADMIN)
def indice(request):
    resumen = [(c, m._meta.verbose_name_plural, m.objects.filter(activo=True).count()) for c, (m, _) in LISTAS.items()]
    return render(request, "catalogos/indice.html", {"resumen": resumen})


@rol_requerido(*SOLO_ADMIN)
def lista(request, clave):
    modelo, campos = _lista(clave)
    q = request.GET.get("q", "").strip()
    qs = modelo.objects.all()
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | (Q(simbolo__icontains=q) if modelo is Unidad else Q()))
    columnas = [modelo._meta.get_field(c).verbose_name for c in campos]
    filas = [(o, [getattr(o, c) for c in campos]) for o in qs]
    return render(request, "catalogos/lista.html", {
        "clave": clave, "titulo": modelo._meta.verbose_name_plural, "singular": modelo._meta.verbose_name,
        "columnas": columnas, "filas": filas, "q": q,
    })


@rol_requerido(*SOLO_ADMIN)
def editar(request, clave, pk=None):
    modelo, campos = _lista(clave)
    obj = get_object_or_404(modelo, pk=pk) if pk else None
    Formulario = forms.modelform_factory(modelo, fields=campos)
    form = Formulario(request.POST or None, instance=obj)
    if obj is None:
        form.fields.pop("activo", None)
    if request.method == "POST" and form.is_valid():
        guardado = form.save()
        messages.success(request, f"Se guardó «{guardado}» en {modelo._meta.verbose_name_plural}.")
        return redirect("catalogos:lista", clave=clave)
    return render(request, "core/form.html", {
        "form": form,
        "titulo": f"Editar {modelo._meta.verbose_name}" if obj else f"{'Nuevo' if modelo is Proveedor else 'Nueva'} {modelo._meta.verbose_name}",
        "migas": [("Listas controladas", reverse("catalogos:indice")),
                  (str(modelo._meta.verbose_name_plural).capitalize(), reverse("catalogos:lista", args=[clave]))],
        "volver": reverse("catalogos:lista", args=[clave]),
    })
