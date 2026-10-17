from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.alertas.estado import con_estado
from apps.catalogos.models import Area, Marca, Ubicacion
from apps.core.exportar import exportar, libro_excel
from apps.core.qr import qr_svg, url_publica_equipo
from apps.cuentas.models import Configuracion, Usuario
from apps.cuentas.permisos import EDITORES, rol_requerido
from apps.servicios.calculos import Estado
from apps.servicios.models import TipoServicio

from . import importar as imp
from .acceso import equipos_visibles
from .forms import CambioEstadoForm, DocumentoForm, EquipoForm, ImportarForm, PuntosFormSet
from .models import Criticidad, Equipo, EstadoEquipo

FILTROS = ("q", "area", "marca", "ubicacion", "responsable", "lote", "criticidad", "estado", "estado_cal")


def filtrar(request):
    """RF-10: buscar y filtrar equipos por todos los criterios del requerimiento."""
    g = request.GET
    f = {k: g.get(k, "").strip() for k in FILTROS}
    qs = con_estado(equipos_visibles(request.user, Equipo.objects.select_related(
        "marca", "ubicacion", "responsable", "unidad", "area__laboratorio")))
    if f["q"]:
        qs = qs.filter(Q(codigo__icontains=f["q"]) | Q(descripcion__icontains=f["q"]) |
                       Q(numero_serie__icontains=f["q"]) | Q(patrimonio__icontains=f["q"]) |
                       Q(modelo__icontains=f["q"]) | Q(servicios__numero_certificado__icontains=f["q"])).distinct()
    if f["area"].startswith("lab-") and f["area"][4:].isdigit():
        qs = qs.filter(area__laboratorio_id=f["area"][4:])
    for campo in ("area", "marca", "ubicacion", "responsable"):
        if f[campo].isdigit():
            qs = qs.filter(**{f"{campo}_id": f[campo]})
    if f["lote"].isdigit():
        qs = qs.filter(lotes__id=f["lote"])
    if f["criticidad"] in Criticidad.values:
        qs = qs.filter(criticidad=f["criticidad"])
    if f["estado"] in EstadoEquipo.values:
        qs = qs.filter(estado=f["estado"])
    elif f["estado"] != "todos":
        qs = qs.exclude(estado=EstadoEquipo.BAJA)  # por defecto no se listan los de baja
    if f["estado_cal"] in Estado.ETIQUETAS:
        qs = qs.filter(estado_cal=f["estado_cal"])
    return qs, f


@login_required
def lista(request):
    qs, f = filtrar(request)
    formato = request.GET.get("formato")
    if formato in ("csv", "xlsx"):
        return exportar_inventario(qs, formato)
    from apps.plan.models import Lote

    pagina = Paginator(qs, 25).get_page(request.GET.get("page"))
    consulta = request.GET.copy()
    consulta.pop("page", None)
    return render(request, "equipos/lista.html", {
        "pagina": pagina, "f": f, "consulta": consulta.urlencode(), "total": pagina.paginator.count,
        "areas": areas_del_usuario(request.user), "marcas": Marca.objects.all(), "ubicaciones": Ubicacion.objects.all(),
        "responsables": Usuario.objects.exclude(rol="consulta"), "lotes": Lote.objects.all(),
        "criticidades": Criticidad.choices, "estados": EstadoEquipo.choices,
        "estados_cal": Estado.ETIQUETAS.items(), "hoy": timezone.localdate(),
    })


def areas_del_usuario(usuario):
    areas = Area.objects.select_related("laboratorio")
    return areas if usuario.ve_todas_las_areas else areas.filter(pk__in=usuario.areas_permitidas())


def exportar_inventario(qs, formato):
    enc = ["Código", "Patrimonio", "Descripción", "Marca", "Modelo", "N.º de serie", "Laboratorio", "Área",
           "Ubicación", "Responsable",
           "Unidad", "Rango desde", "Rango hasta", "Resolución", "Capacidad", "Tolerancia", "Criticidad",
           "Intervalo (meses)", "Estado actual", "Próxima calibración", "Estado de calibración"]
    filas = [[e.codigo, e.patrimonio, e.descripcion, e.marca.nombre, e.modelo, e.numero_serie,
              e.area.laboratorio.nombre if e.area else "", e.area.nombre if e.area else "", e.ubicacion.nombre,
              e.responsable.username, e.unidad.simbolo, e.rango_min, e.rango_max, e.resolucion, e.capacidad,
              e.tolerancia, e.get_criticidad_display(), e.intervalo_meses, e.get_estado_display(), e.proxima,
              Estado.ETIQUETAS[e.estado_cal]] for e in qs]
    return exportar(formato, f"inventario_{timezone.localdate():%Y-%m-%d}", enc, filas)


@login_required
def ficha(request, pk):
    equipo = get_object_or_404(con_estado(equipos_visibles(request.user, Equipo.objects.select_related(
        "marca", "ubicacion", "responsable", "unidad", "asignado_a", "area__laboratorio"))), pk=pk)
    servicios = equipo.servicios.select_related("proveedor", "registrado_por").prefetch_related("puntos")
    ultima_cal = servicios.filter(tipo=TipoServicio.CALIBRACION).first()
    vigencias = [s for s in servicios.exclude(tipo=TipoServicio.CALIBRACION)
                 if s.vigencia_hasta and s == servicios.filter(tipo=s.tipo).first()]
    return render(request, "equipos/ficha.html", {
        "e": equipo, "servicios": servicios, "ultima_cal": ultima_cal, "vigencias": vigencias,
        "puntos": equipo.puntos.filter(activo=True), "cambios": equipo.cambios_estado.select_related("usuario"),
        "documentos": equipo.documentos.all(), "novedades": equipo.novedades.select_related("responsable")[:20],
        "planes_mant": equipo.planes_mantenimiento.filter(activo=True),
        "instrumentos": equipo.instrumentos.all(), "lotes": equipo.lotes.all(),
        "versiones": equipo.versiones()[:30], "estado_txt": Estado.ETIQUETAS[equipo.estado_cal],
        "dias": (equipo.proxima - timezone.localdate()).days if equipo.proxima else None,
        "plazo": Configuracion.actual().plazo_aviso_dias, "hoy": timezone.localdate(),
    })


def _guardar_equipo(request, equipo=None):
    form = EquipoForm(request.POST or None, instance=equipo, usuario=request.user)
    formset = PuntosFormSet(request.POST or None, instance=equipo or Equipo(), prefix="puntos")
    if request.method == "POST":
        form_ok = form.is_valid()
        if form_ok:
            formset.instance = form.instance
        if form_ok and formset.is_valid():
            with transaction.atomic():
                nuevo = form.save()
                for p in formset.save(commit=False):
                    p.equipo = nuevo
                    p.save()
            messages.success(request, f"Se guardó el equipo {nuevo.codigo}.")
            return redirect(nuevo)
    return render(request, "equipos/form.html", {"form": form, "formset": formset, "equipo": equipo})


@rol_requerido(*EDITORES)
def crear(request):
    return _guardar_equipo(request)


@rol_requerido(*EDITORES)
def editar(request, pk):
    return _guardar_equipo(request, get_object_or_404(equipos_visibles(request.user), pk=pk))


@rol_requerido(*EDITORES)
def cambiar_estado(request, pk):
    """RF-11 y RNF-16: cambio de estado con confirmación, fecha, motivo y persona."""
    equipo = get_object_or_404(equipos_visibles(request.user), pk=pk)
    form = CambioEstadoForm(request.POST or None, equipo=equipo, initial={"fecha": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        equipo.cambiar_estado(d["estado_nuevo"], d["motivo"], request.user, d["fecha"])
        messages.success(request, f"{equipo.codigo} pasó a «{equipo.get_estado_display()}».")
        return redirect(equipo)
    return render(request, "core/form.html", {
        "form": form, "titulo": f"Cambiar el estado de {equipo.codigo}",
        "subtitulo": f"Estado actual: {equipo.get_estado_display()}. Un equipo de baja no se borra: conserva todo su historial.",
        "migas": [("Equipos", reverse("equipos:lista")), (equipo.codigo, equipo.get_absolute_url())],
        "volver": equipo.get_absolute_url(), "boton": "Cambiar el estado",
    })


@rol_requerido(*EDITORES)
def subir_documento(request, pk):
    """RF-13: fotografía y documentos del equipo."""
    equipo = get_object_or_404(equipos_visibles(request.user), pk=pk)
    form = DocumentoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        doc = form.save(commit=False)
        doc.equipo, doc.subido_por = equipo, request.user
        doc.save()
        messages.success(request, f"Se adjuntó «{doc.titulo}».")
        return redirect(equipo)
    return render(request, "core/form.html", {
        "form": form, "titulo": f"Adjuntar un documento a {equipo.codigo}",
        "migas": [("Equipos", reverse("equipos:lista")), (equipo.codigo, equipo.get_absolute_url())],
        "volver": equipo.get_absolute_url(), "boton": "Adjuntar",
    })


@login_required
def etiqueta(request, pk):
    """RF-14: etiqueta con código QR; al escanearla se ven los datos del equipo sin iniciar sesión."""
    equipo = get_object_or_404(con_estado(equipos_visibles(request.user)), pk=pk)
    url = url_publica_equipo(equipo)
    svg = qr_svg(url)
    return render(request, "equipos/etiqueta.html", {"e": equipo, "svg": svg, "url": url,
                                                      "estado_txt": Estado.ETIQUETAS[equipo.estado_cal]})


SESION_IMPORTACION = "importacion_equipos"


@rol_requerido(*EDITORES)
def importar(request):
    """RF-12: revisar el archivo, mostrar errores y guardar todo junto solo si no hay ninguno."""
    if request.method == "POST" and "confirmar" in request.POST:
        datos = request.session.pop(SESION_IMPORTACION, None)
        if not datos:
            messages.error(request, "La revisión expiró. Vuelve a subir el archivo.")
            return redirect("equipos:importar")
        filas = [imp.Fila(n, d) for n, d in datos]
        try:
            with transaction.atomic():
                creados = imp.guardar(filas, request.user)
        except ValueError as e:
            messages.error(request, f"No se guardó ningún equipo. {e}")
            return redirect("equipos:importar")
        messages.success(request, f"Se cargaron {len(creados)} equipos.")
        return redirect("equipos:lista")

    form = ImportarForm(request.POST or None, request.FILES or None)
    filas = None
    if request.method == "POST" and form.is_valid():
        try:
            filas = imp.validar(imp.leer(form.cleaned_data["archivo"]), request.user)
        except Exception:  # archivo dañado o con otro formato
            form.add_error("archivo", "No se pudo leer el archivo. Revisa que sea la plantilla en .xlsx o .csv.")
        if filas is not None:
            if not filas:
                form.add_error("archivo", "El archivo no tiene filas de equipos.")
                filas = None
            elif not any(f.errores for f in filas):
                request.session[SESION_IMPORTACION] = [(f.numero, f.datos) for f in filas]
    con_errores = sum(1 for f in filas or [] if f.errores)
    return render(request, "equipos/importar.html", {"form": form, "filas": filas, "con_errores": con_errores})


@rol_requerido(*EDITORES)
def plantilla(request):
    wb = libro_excel([
        ("equipos", imp.ENCABEZADOS, [["EQ-0100", "PAT-123", "Balanza analítica 220 g", "Marca A", "BA-220",
                                       "SN-0001", "Laboratorio Central", "Metrología", "Sala de balanzas", "mperez", "g", "0", "220", "0,0001", "220",
                                       "", "Alta", "12"]]),
        ("instrucciones", ["Columna", "Qué escribir"], [[c, d] for c, _, d in imp.COLUMNAS]),
    ])
    buf = BytesIO()
    wb.save(buf)
    r = HttpResponse(buf.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r["Content-Disposition"] = 'attachment; filename="plantilla_equipos.xlsx"'
    return r
