from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.alertas.estado import activos
from apps.cuentas.permisos import EDITORES, rol_requerido
from apps.equipos.acceso import equipos_visibles
from apps.equipos.models import ORDEN_CRITICIDAD
from apps.servicios.calculos import Estado

from .forms import EjecucionForm, ItemPlanForm, LoteForm, PlanForm
from .models import ItemPlan, Lote, PlanAnual


def _form(request, form, titulo, migas, volver, subtitulo=""):
    return render(request, "core/form.html", {"form": form, "titulo": titulo, "migas": migas, "volver": volver,
                                              "subtitulo": subtitulo})


@login_required
def indice(request):
    planes = PlanAnual.objects.all()
    resumen = [(p, p.avance()) for p in planes]
    return render(request, "plan/indice.html", {"resumen": resumen, "lotes": Lote.objects.prefetch_related("equipos")})


@login_required
def lote(request, pk):
    obj = get_object_or_404(Lote, pk=pk)
    equipos = activos(equipos_visibles(request.user, obj.equipos.all())).select_related("responsable")
    return render(request, "plan/lote.html", {"l": obj, "equipos": equipos,
                                              "items": obj.items_plan.select_related("plan", "proveedor")})


@rol_requerido(*EDITORES)
def lote_editar(request, pk=None):
    obj = get_object_or_404(Lote, pk=pk) if pk else None
    form = LoteForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        guardado = form.save()
        messages.success(request, f"Se guardó el lote {guardado.codigo}.")
        return redirect(guardado)
    return _form(request, form, f"Editar lote {obj.codigo}" if obj else "Nuevo lote",
                 [("Plan y presupuesto", reverse("plan:indice"))],
                 obj.get_absolute_url() if obj else reverse("plan:indice"),
                 "Un lote agrupa equipos que se planifican, contratan y calibran juntos.")


@login_required
def plan(request, pk):
    obj = get_object_or_404(PlanAnual, pk=pk)
    items = obj.items.select_related("lote", "proveedor")
    return render(request, "plan/plan.html", {"p": obj, "items": items, "a": obj.avance()})


@rol_requerido(*EDITORES)
def plan_editar(request, pk=None):
    obj = get_object_or_404(PlanAnual, pk=pk) if pk else None
    form = PlanForm(request.POST or None, instance=obj, initial={"ejercicio": timezone.localdate().year + 1})
    if request.method == "POST" and form.is_valid():
        guardado = form.save()
        messages.success(request, f"Se guardó el {guardado}.")
        return redirect(guardado)
    return _form(request, form, f"Editar {obj}" if obj else "Nuevo plan anual",
                 [("Plan y presupuesto", reverse("plan:indice"))],
                 obj.get_absolute_url() if obj else reverse("plan:indice"))


@rol_requerido(*EDITORES)
def item_editar(request, plan_pk, pk=None):
    p = get_object_or_404(PlanAnual, pk=plan_pk)
    obj = get_object_or_404(ItemPlan, pk=pk, plan=p) if pk else None
    form = ItemPlanForm(request.POST or None, instance=obj, plan=p)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.plan = p
        if not item.pk and not item.proveedor_id:
            item.proveedor = item.lote.proveedor
        item.save()
        messages.success(request, f"Se guardó el lote {item.lote.codigo} en el {p}.")
        return redirect(p)
    return _form(request, form, f"Programar un lote en el {p}" if not obj else f"Editar {obj}",
                 [("Plan y presupuesto", reverse("plan:indice")), (str(p), p.get_absolute_url())], p.get_absolute_url(),
                 "Indica el mes previsto de contratación y el monto (RF-30).")


@rol_requerido(*EDITORES)
def ejecucion(request, pk):
    item = get_object_or_404(ItemPlan.objects.select_related("plan", "lote"), pk=pk)
    form = EjecucionForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Se actualizó la ejecución de {item.lote.codigo}.")
        return redirect(item.plan)
    return _form(request, form, f"Ejecución de {item.lote}",
                 [("Plan y presupuesto", reverse("plan:indice")), (str(item.plan), item.plan.get_absolute_url())],
                 item.plan.get_absolute_url())


@login_required
def prioridad(request):
    """RF-33: orden de prioridad sugerido para calibrar, según criticidad y vencimiento."""
    hoy = timezone.localdate()
    try:
        anio = int(request.GET.get("anio", hoy.year))
    except ValueError:
        anio = hoy.year
    equipos = [e for e in activos(equipos_visibles(request.user)).select_related("responsable", "ubicacion").prefetch_related("lotes")
               if e.estado_cal in (Estado.VENCIDO, Estado.SIN_REGISTRO) or (e.proxima and e.proxima.year <= anio)]
    equipos.sort(key=lambda e: (
        {Estado.VENCIDO: 0, Estado.SIN_REGISTRO: 1}.get(e.estado_cal, 2),
        ORDEN_CRITICIDAD.get(e.criticidad, 9),
        e.proxima or hoy,
    ))
    return render(request, "plan/prioridad.html", {"equipos": equipos, "anio": anio, "hoy": hoy})
