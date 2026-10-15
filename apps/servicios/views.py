from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import Proveedor
from apps.core.exportar import exportar
from apps.cuentas.permisos import EDITORES, rol_requerido
from apps.equipos.models import Equipo, EstadoEquipo

from .calculos import DatoFaltante
from .forms import (DecisionForm, ElegirEquipoForm, PuntoMedidoForm, PuntosFormSet, PuntosMedidosFormSet,
                    ServicioForm)
from .models import Decision, PuntoMedido, Resultado, Servicio, TipoServicio


def _datos_iniciales(equipo):
    """Un renglón por cada punto activo de la ficha, con su EMP (copiado en el servicio, RN-06)."""
    return list(equipo.puntos.filter(activo=True).order_by("orden", "valor_nominal"))


def _pantalla(request, form, formset, equipo, servicio=None):
    return render(request, "servicios/form.html", {
        "form": form, "formset": formset, "equipo": equipo, "servicio": servicio,
        "puntos_ficha": _datos_iniciales(equipo) if servicio is None else None,
    })


def _despues_de_guardar(request, servicio):
    if servicio.es_calibracion and servicio.resultado == Resultado.NO_CONFORME and not hasattr(servicio, "decision"):
        messages.warning(request, "El equipo resultó NO APTO. Decide qué hacer con él antes de seguir (RN-05).")
        return redirect("servicios:decision", pk=servicio.pk)
    messages.success(request, f"Se guardó la {servicio.get_tipo_display().lower()} {servicio.numero_certificado}: {servicio.dictamen}.")
    return redirect(servicio)


@rol_requerido(*EDITORES)
def crear(request):
    equipo_id = request.GET.get("equipo")
    if not equipo_id:
        elegir = ElegirEquipoForm(request.GET or None)
        return render(request, "core/form.html", {
            "form": elegir, "titulo": "Registrar un servicio", "subtitulo": "Elige el equipo que recibió el servicio.",
            "migas": [("Servicios", reverse("servicios:lista"))], "boton": "Continuar", "metodo_get": True,
            "volver": reverse("servicios:lista"),
        })
    equipo = get_object_or_404(Equipo.objects.exclude(estado=EstadoEquipo.BAJA), pk=equipo_id)
    puntos = _datos_iniciales(equipo)
    form = ServicioForm(request.POST or None, request.FILES or None, equipo=equipo,
                        initial={"fecha": timezone.localdate()})
    PuntosAlta = inlineformset_factory(Servicio, PuntoMedido, form=PuntoMedidoForm, formset=PuntosMedidosFormSet,
                                       extra=len(puntos), can_delete=False)
    formset = PuntosAlta(request.POST or None, instance=Servicio(), prefix="puntos",
                         initial=[{"valor_referencia": f"{p.valor_nominal.normalize():f}"} for p in puntos])
    if request.method == "POST" and form.is_valid():
        es_cal = form.cleaned_data["tipo"] == TipoServicio.CALIBRACION
        if es_cal and not puntos:
            form.add_error(None, "El equipo no tiene puntos a calibrar con su EMP. Agrégalos en la ficha del equipo.")
        elif not es_cal or formset.is_valid():
            try:
                with transaction.atomic():
                    servicio = form.save(commit=False)
                    servicio.equipo, servicio.registrado_por = equipo, request.user
                    servicio.save()
                    if es_cal:
                        for i, f in enumerate(formset.forms):
                            if not f.tiene_datos():
                                continue
                            p = f.save(commit=False)
                            p.servicio, p.orden = servicio, i + 1
                            p.emp_tipo, p.emp_valor = puntos[i].emp_tipo, puntos[i].emp_valor
                            p.save()
                        servicio.recalcular(form.cleaned_data.get("proxima_manual"),
                                            form.cleaned_data.get("justificacion_proxima", ""))
                return _despues_de_guardar(request, servicio)
            except DatoFaltante as e:
                form.add_error(None, str(e))
    return _pantalla(request, form, formset, equipo)


@rol_requerido(*EDITORES)
def corregir(request, pk):
    """RF-24: la corrección crea una versión nueva y conserva la anterior con fecha, usuario y motivo."""
    servicio = get_object_or_404(Servicio.objects.select_related("equipo"), pk=pk)
    form = ServicioForm(request.POST or None, request.FILES or None, instance=servicio, equipo=servicio.equipo)
    formset = PuntosFormSet(request.POST or None, instance=servicio, prefix="puntos")
    if request.method == "POST" and form.is_valid() and (not servicio.es_calibracion or formset.is_valid()):
        try:
            with transaction.atomic():
                motivo = form.cleaned_data["motivo"]
                servicio = form.save()
                if servicio.es_calibracion:
                    for p in formset.save(commit=False):
                        p._change_reason = motivo
                        p.save()
                    servicio._change_reason = motivo
                    servicio.recalcular(form.cleaned_data.get("proxima_manual"),
                                        form.cleaned_data.get("justificacion_proxima", ""))
            return _despues_de_guardar(request, servicio)
        except DatoFaltante as e:
            form.add_error(None, str(e))
    return _pantalla(request, form, formset, servicio.equipo, servicio)


@login_required
def detalle(request, pk):
    s = get_object_or_404(Servicio.objects.select_related("equipo__unidad", "proveedor", "registrado_por"), pk=pk)
    return render(request, "servicios/detalle.html", {
        "s": s, "puntos": s.puntos.all(), "versiones": s.versiones()[:30],
        "decision": getattr(s, "decision", None), "evaluacion": getattr(s, "evaluacion", None),
        "anterior": s.ultima_conforme_anterior() if s.resultado == Resultado.NO_CONFORME else None,
        "no_cumplen": s.puntos.filter(cumple=False).count(),
    })


@rol_requerido(*EDITORES)
def decision(request, pk):
    """RN-05 / RF-22: proponer «fuera de servicio», pedir confirmación y registrar quién decidió."""
    s = get_object_or_404(Servicio.objects.select_related("equipo"), pk=pk, tipo=TipoServicio.CALIBRACION,
                          resultado=Resultado.NO_CONFORME)
    if hasattr(s, "decision"):
        messages.info(request, "Esta decisión ya fue registrada.")
        return redirect(s)
    anterior = s.ultima_conforme_anterior()
    form = DecisionForm(request.POST or None, initial={"decision": Decision.FUERA_DE_SERVICIO})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            d = form.save(commit=False)
            d.servicio, d.decidido_por = s, request.user
            d.fuera_tolerancia_desde = anterior.fecha if anterior else None
            d.save()
            if d.decision == Decision.FUERA_DE_SERVICIO:
                s.equipo.cambiar_estado(EstadoEquipo.FUERA_DE_SERVICIO,
                                        f"Calibración no apta {s.numero_certificado}", request.user, s.fecha)
        messages.success(request, "Se registró la decisión. Evalúa el efecto sobre los resultados emitidos (RF-35).")
        return redirect(s)
    return render(request, "servicios/decision.html", {"s": s, "form": form, "anterior": anterior,
                                                        "no_cumplen": s.puntos.filter(cumple=False)})


@login_required
def lista(request):
    g = request.GET
    f = {k: g.get(k, "").strip() for k in ("q", "tipo", "resultado", "proveedor", "desde", "hasta")}
    qs = Servicio.objects.select_related("equipo", "proveedor")
    if f["q"]:
        qs = qs.filter(Q(equipo__codigo__icontains=f["q"]) | Q(equipo__descripcion__icontains=f["q"]) |
                       Q(numero_certificado__icontains=f["q"]))
    if f["tipo"] in TipoServicio.values:
        qs = qs.filter(tipo=f["tipo"])
    if f["resultado"] in Resultado.values:
        qs = qs.filter(resultado=f["resultado"])
    if f["proveedor"].isdigit():
        qs = qs.filter(proveedor_id=f["proveedor"])
    if f["desde"]:
        qs = qs.filter(fecha__gte=f["desde"])
    if f["hasta"]:
        qs = qs.filter(fecha__lte=f["hasta"])
    if g.get("formato") in ("csv", "xlsx"):
        enc = ["Fecha", "Equipo", "Descripción", "Tipo", "N.º de certificado", "Proveedor", "Resultado",
               "Regla", "Próxima calibración", "Vigente hasta"]
        filas = [[s.fecha, s.equipo.codigo, s.equipo.descripcion, s.get_tipo_display(), s.numero_certificado,
                  s.proveedor.nombre, s.dictamen, s.get_regla_display() if s.es_calibracion else "",
                  s.proxima_fecha, s.vigencia_hasta] for s in qs]
        return exportar(g["formato"], f"servicios_{timezone.localdate():%Y-%m-%d}", enc, filas)
    pagina = Paginator(qs, 25).get_page(g.get("page"))
    consulta = g.copy()
    consulta.pop("page", None)
    return render(request, "servicios/lista.html", {
        "pagina": pagina, "f": f, "consulta": consulta.urlencode(), "tipos": TipoServicio.choices,
        "resultados": Resultado.choices, "proveedores": Proveedor.objects.all(),
    })
