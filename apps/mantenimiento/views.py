from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.permisos import EDITORES, rol_requerido
from apps.equipos.models import Equipo, EstadoEquipo
from apps.servicios.calculos import sumar_meses
from apps.servicios.models import Resultado, Servicio, TipoServicio

from .forms import EvaluacionForm, NovedadForm, PlanMantenimientoForm
from .models import Novedad, PlanMantenimiento, TipoNovedad


def tareas_con_vencimiento(hoy=None):
    """RF-34: cada tarea activa con la fecha de su próxima ejecución (desde la última novedad que la cumplió)."""
    hoy = hoy or timezone.localdate()
    tareas = []
    planes = (PlanMantenimiento.objects.filter(activo=True).exclude(equipo__estado=EstadoEquipo.BAJA)
              .select_related("equipo", "responsable").prefetch_related("ejecuciones"))
    for t in planes:
        ultima = max((n.fecha for n in t.ejecuciones.all()), default=None)
        t.ultima = ultima
        t.proxima = sumar_meses(ultima, t.frecuencia_meses) if ultima else None
        t.atrasada = t.proxima is None or t.proxima <= hoy
        tareas.append(t)
    tareas.sort(key=lambda t: (not t.atrasada, t.proxima or hoy))
    return tareas


def evaluaciones_pendientes():
    """RF-35: calibraciones no aptas que todavía no tienen la evaluación del efecto."""
    return (Servicio.objects.filter(tipo=TipoServicio.CALIBRACION, resultado=Resultado.NO_CONFORME,
                                    evaluacion__isnull=True).select_related("equipo"))


@login_required
def indice(request):
    g = request.GET
    tipo = g.get("tipo", "")
    novedades = Novedad.objects.select_related("equipo", "responsable")
    if tipo in TipoNovedad.values:
        novedades = novedades.filter(tipo=tipo)
    q = g.get("q", "").strip()
    if q:
        novedades = novedades.filter(equipo__codigo__icontains=q) | novedades.filter(descripcion__icontains=q)
    return render(request, "mantenimiento/indice.html", {
        "tareas": tareas_con_vencimiento(), "pendientes": evaluaciones_pendientes(),
        "pagina": Paginator(novedades, 25).get_page(g.get("page")), "tipos": TipoNovedad.choices,
        "tipo": tipo, "q": q,
    })


def _form(request, form, titulo, equipo, subtitulo=""):
    return render(request, "core/form.html", {
        "form": form, "titulo": titulo, "subtitulo": subtitulo, "volver": equipo.get_absolute_url(),
        "migas": [("Equipos", reverse("equipos:lista")), (equipo.codigo, equipo.get_absolute_url())],
    })


@rol_requerido(*EDITORES)
def novedad_editar(request, equipo_pk=None, pk=None):
    obj = get_object_or_404(Novedad.objects.select_related("equipo"), pk=pk) if pk else None
    equipo = obj.equipo if obj else get_object_or_404(Equipo, pk=equipo_pk)
    inicial = {"fecha": timezone.localdate(), "responsable": request.user, "plan": request.GET.get("plan")}
    form = NovedadForm(request.POST or None, instance=obj, equipo=equipo, initial=inicial)
    if request.method == "POST" and form.is_valid():
        n = form.save(commit=False)
        n.equipo = equipo
        n.save()
        messages.success(request, f"Se registró la novedad en {equipo.codigo}.")
        return redirect(equipo)
    return _form(request, form, "Corregir novedad" if obj else f"Registrar novedad en {equipo.codigo}", equipo,
                 "Mantenimientos, verificaciones intermedias, daños, fallas, modificaciones o reparaciones (RF-34).")


@rol_requerido(*EDITORES)
def plan_editar(request, equipo_pk=None, pk=None):
    obj = get_object_or_404(PlanMantenimiento.objects.select_related("equipo"), pk=pk) if pk else None
    equipo = obj.equipo if obj else get_object_or_404(Equipo, pk=equipo_pk)
    form = PlanMantenimientoForm(request.POST or None, instance=obj, initial={"responsable": equipo.responsable_id})
    if request.method == "POST" and form.is_valid():
        t = form.save(commit=False)
        t.equipo = equipo
        t.save()
        messages.success(request, f"Se guardó la tarea «{t.actividad}» de {equipo.codigo}.")
        return redirect(equipo)
    return _form(request, form, "Editar tarea de mantenimiento" if obj else f"Plan de mantenimiento de {equipo.codigo}",
                 equipo)


@login_required
def evaluacion(request, servicio_pk):
    """RF-35: evaluación del efecto sobre los resultados emitidos mientras el equipo pudo estar fuera de tolerancia."""
    s = get_object_or_404(Servicio.objects.select_related("equipo"), pk=servicio_pk,
                          tipo=TipoServicio.CALIBRACION, resultado=Resultado.NO_CONFORME)
    obj = getattr(s, "evaluacion", None)
    editar = request.user.puede_editar and (obj is None or request.GET.get("corregir") or request.method == "POST")
    if not editar:
        if obj is None:
            messages.info(request, "Esta calibración todavía no tiene la evaluación del efecto.")
            return redirect(s)
        return render(request, "mantenimiento/evaluacion.html", {"s": s, "ev": obj, "versiones": obj.versiones()[:20]})
    decision = getattr(s, "decision", None)
    anterior = s.ultima_conforme_anterior()
    desde = decision.fuera_tolerancia_desde if decision else (anterior.fecha if anterior else None)
    form = EvaluacionForm(request.POST or None, instance=obj,
                          initial={"desde": desde, "hasta": s.fecha, "fecha": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        ev = form.save(commit=False)
        ev.servicio = s
        ev.evaluado_por = request.user
        ev.save()
        messages.success(request, "Se registró la evaluación del efecto.")
        return redirect(s)
    return render(request, "core/form.html", {
        "form": form, "titulo": f"Evaluación del efecto · {s.equipo.codigo}",
        "subtitulo": "Revisa los ensayos o informes emitidos desde la última calibración conforme hasta este no apto.",
        "migas": [("Calibraciones", reverse("servicios:lista")), (s.numero_certificado, s.get_absolute_url())],
        "volver": s.get_absolute_url(),
    })
