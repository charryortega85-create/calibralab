"""Módulo G: hoja de vida en PDF (RF-36), estado y vencimientos (RF-37), ejecución y presupuesto (RF-38)."""
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.utils import timezone

from apps.alertas.estado import activos, con_estado
from apps.core.exportar import exportar, libro_excel, respuesta_csv
from apps.equipos.models import ORDEN_CRITICIDAD, Equipo, EstadoEquipo
from apps.plan.models import MESES, EstadoEjecucion, PlanAnual
from apps.servicios.calculos import Estado

FORMATOS = ("csv", "xlsx")
HORIZONTES = (30, 60, 90)
URGENCIA = [Estado.VENCIDO, Estado.SIN_REGISTRO, Estado.POR_VENCER, Estado.VIGENTE]


@login_required
def indice(request):
    return render(request, "reportes/indice.html", {
        "planes": PlanAnual.objects.all(), "equipos": Equipo.objects.only("pk", "codigo", "descripcion"),
        "horizontes": HORIZONTES,
    })


# --- RF-36: hoja de vida -------------------------------------------------------------------------------

def datos_hoja_vida(equipo):
    servicios = equipo.servicios.select_related("proveedor", "registrado_por").prefetch_related("puntos")
    return {
        "e": equipo, "servicios": servicios, "puntos": equipo.puntos.filter(activo=True),
        "cambios": equipo.cambios_estado.select_related("usuario"),
        "novedades": equipo.novedades.select_related("responsable", "plan"),
        "planes_mant": equipo.planes_mantenimiento.select_related("responsable"),
        "decisiones": [s.decision for s in servicios if hasattr(s, "decision")],
        "evaluaciones": [s.evaluacion for s in servicios if hasattr(s, "evaluacion")],
        "documentos": equipo.documentos.all(), "estado_txt": Estado.ETIQUETAS[equipo.estado_cal],
        "generado": timezone.localtime(),
    }


@login_required
def hoja_vida(request, pk):
    equipo = get_object_or_404(con_estado(Equipo.objects.select_related(
        "marca", "ubicacion", "responsable", "unidad", "asignado_a")), pk=pk)
    contexto = datos_hoja_vida(equipo)
    if request.GET.get("formato") == "html":
        return render(request, "reportes/hoja_vida.html", contexto)
    from weasyprint import HTML  # se importa aquí: carga bibliotecas gráficas pesadas

    html = render_to_string("reportes/hoja_vida.html", contexto, request=request)
    pdf = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
    r = HttpResponse(pdf, content_type="application/pdf")
    r["Content-Disposition"] = f'inline; filename="hoja_de_vida_{equipo.codigo}.pdf"'
    return r


# --- RF-37: estado y vencimientos ----------------------------------------------------------------------

def _tabla(request, titulo, subtitulo, encabezados, filas, nombre, filtros="", resumen=None):
    formato = request.GET.get("formato")
    if formato in FORMATOS:
        return exportar(formato, nombre, encabezados, filas)
    consulta = request.GET.copy()
    consulta.pop("formato", None)
    return render(request, "reportes/tabla.html", {
        "titulo": titulo, "subtitulo": subtitulo, "encabezados": encabezados, "filas": filas,
        "consulta": consulta.urlencode(), "filtros": filtros, "resumen": resumen or [],
    })


def _fila_estado(e, hoy):
    dias = (e.proxima - hoy).days if e.proxima else None
    return [e.codigo, e.descripcion, str(e.ubicacion or ""), str(e.responsable), e.get_criticidad_display(),
            e.get_estado_display(), Estado.ETIQUETAS[e.estado_cal], e.proxima, dias]


ENC_ESTADO = ["Código", "Equipo", "Ubicación", "Responsable", "Criticidad", "Estado del equipo",
              "Estado de calibración", "Próxima calibración", "Días que faltan"]


@login_required
def estado(request):
    hoy = timezone.localdate()
    filtro = request.GET.get("estado", "")
    incluir_baja = request.GET.get("baja") == "1"
    qs = con_estado(Equipo.objects.select_related("ubicacion", "responsable"))
    if not incluir_baja:
        qs = qs.exclude(estado=EstadoEquipo.BAJA)
    if filtro in URGENCIA:
        qs = qs.filter(estado_cal=filtro)
    equipos = sorted(qs, key=lambda e: (URGENCIA.index(e.estado_cal), ORDEN_CRITICIDAD.get(e.criticidad, 9),
                                        e.proxima or date.min, e.codigo))
    cuenta = {k: 0 for k in URGENCIA}
    for e in equipos:
        cuenta[e.estado_cal] += 1
    filtros = render_to_string("reportes/_filtro_estado.html", {
        "estados": [(k, Estado.ETIQUETAS[k]) for k in URGENCIA], "filtro": filtro, "baja": incluir_baja})
    return _tabla(request, "Estado de los equipos", f"Al {hoy:%Y-%m-%d}. Ordenado por urgencia y criticidad.",
                  ENC_ESTADO, [_fila_estado(e, hoy) for e in equipos], f"estado_equipos_{hoy:%Y-%m-%d}", filtros,
                  [(Estado.ETIQUETAS[k], v) for k, v in cuenta.items()])


@login_required
def vencimientos(request):
    hoy = timezone.localdate()
    try:
        dias = int(request.GET.get("dias", 90))
    except ValueError:
        dias = 90
    dias = dias if dias in HORIZONTES else 90
    con_vencidos = request.GET.get("vencidos", "1") == "1"
    limite = hoy + timedelta(days=dias)
    qs = activos(Equipo.objects.select_related("ubicacion", "responsable"), dia=hoy)
    equipos = [e for e in qs if (e.proxima and hoy <= e.proxima <= limite) or
               (con_vencidos and e.estado_cal == Estado.VENCIDO)]
    equipos.sort(key=lambda e: (e.proxima or date.min, ORDEN_CRITICIDAD.get(e.criticidad, 9), e.codigo))

    def tramo(e):
        if e.proxima is None or e.proxima < hoy:
            return "Vencido"
        d = (e.proxima - hoy).days
        return next(f"Hasta {h} días" for h in HORIZONTES if d <= h)

    filas = [_fila_estado(e, hoy) + [tramo(e)] for e in equipos]
    resumen = [(t, sum(1 for f in filas if f[-1] == t)) for t in
               (["Vencido"] if con_vencidos else []) + [f"Hasta {h} días" for h in HORIZONTES if h <= dias]]
    filtros = render_to_string("reportes/_filtro_vencimientos.html", {
        "horizontes": HORIZONTES, "dias": dias, "vencidos": con_vencidos})
    return _tabla(request, f"Vencimientos a {dias} días",
                  f"Calibraciones que vencen entre el {hoy:%Y-%m-%d} y el {limite:%Y-%m-%d}"
                  + (", más las ya vencidas." if con_vencidos else "."),
                  ENC_ESTADO + ["Tramo"], filas, f"vencimientos_{dias}_dias_{hoy:%Y-%m-%d}", filtros, resumen)


# --- RF-38: ejecución por lote y avance presupuestario --------------------------------------------------

ENC_EJECUCION = ["Lote", "Nombre", "Equipos", "Mes previsto", "Monto previsto", "Proveedor",
                 "Estado de ejecución", "N.º de nota de requerimiento", "Fecha de ejecución", "Estado de pago",
                 "Monto pagado"]
ENC_PRESUPUESTO = ["Mes", "Lotes programados", "Lotes ejecutados", "Monto previsto", "Monto pagado",
                   "Previsto acumulado", "Pagado acumulado", "Avance del presupuesto (%)"]


def filas_ejecucion(plan):
    items = plan.items.select_related("lote", "proveedor").prefetch_related("lote__equipos")
    return [[i.lote.codigo, i.lote.nombre, i.lote.equipos.count(), i.get_mes_previsto_display(), i.monto_previsto,
             str(i.proveedor or ""), i.get_estado_ejecucion_display(), i.nota_requerimiento, i.fecha_ejecucion,
             i.get_estado_pago_display(), i.monto_pagado] for i in items]


def filas_presupuesto(plan):
    filas, acum_prev, acum_pag = [], 0, 0
    items = list(plan.items.all())
    for mes, nombre in MESES:
        del_mes = [i for i in items if i.mes_previsto == mes]
        if not del_mes:
            continue
        prev = sum(i.monto_previsto for i in del_mes)
        pag = sum(i.monto_pagado for i in del_mes)
        acum_prev, acum_pag = acum_prev + prev, acum_pag + pag
        filas.append([nombre.capitalize(), len(del_mes), sum(1 for i in del_mes if i.estado_ejecucion == EstadoEjecucion.EJECUTADO),
                      prev, pag, acum_prev, acum_pag, round(acum_pag * 100 / acum_prev, 1) if acum_prev else 0])
    return filas


@login_required
def ejecucion(request):
    planes = PlanAnual.objects.all()
    plan = None
    if str(request.GET.get("plan", "")).isdigit():
        plan = get_object_or_404(PlanAnual, pk=request.GET["plan"])
    else:
        plan = planes.filter(ejercicio=timezone.localdate().year).first() or planes.first()
    hoja = request.GET.get("hoja", "ejecucion")
    formato = request.GET.get("formato")
    if plan is None:
        return render(request, "reportes/ejecucion.html", {"planes": planes})
    ejecucion_filas, presupuesto_filas = filas_ejecucion(plan), filas_presupuesto(plan)
    nombre = f"plan_{plan.ejercicio}"
    if formato == "xlsx":
        from io import BytesIO
        wb = libro_excel([("Ejecución por lote", ENC_EJECUCION, ejecucion_filas),
                          ("Avance presupuestario", ENC_PRESUPUESTO, presupuesto_filas)])
        buf = BytesIO()
        wb.save(buf)
        r = HttpResponse(buf.getvalue(),
                         content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        r["Content-Disposition"] = f'attachment; filename="{nombre}.xlsx"'
        return r
    if formato == "csv":
        if hoja == "presupuesto":
            return respuesta_csv(f"{nombre}_presupuesto", ENC_PRESUPUESTO, presupuesto_filas)
        return respuesta_csv(f"{nombre}_ejecucion", ENC_EJECUCION, ejecucion_filas)
    return render(request, "reportes/ejecucion.html", {
        "planes": planes, "plan": plan, "a": plan.avance(),
        "enc_ejecucion": ENC_EJECUCION, "ejecucion": ejecucion_filas,
        "enc_presupuesto": ENC_PRESUPUESTO, "presupuesto": presupuesto_filas,
    })
