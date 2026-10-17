from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.conf import settings
from django.db.models import Count, OuterRef, Q, Subquery, Sum
from django.forms import inlineformset_factory
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.catalogos.models import Proveedor
from apps.core.exportar import exportar
from apps.core.qr import qr_svg, url_publica_certificado
from apps.cuentas.permisos import EDITORES, SOLO_ADMIN, rol_requerido
from apps.equipos.acceso import del_usuario, equipos_visibles
from apps.equipos.models import Equipo, EstadoEquipo

from . import ia
from .calculos import DatoFaltante
from .forms import (AnexoForm, DecisionForm, ElegirEquipoForm, PuntoMedidoForm, PuntosFormSet, PuntosMedidosFormSet,
                    ServicioForm, patrones_formset)
from .models import Decision, LecturaIA, PuntoMedido, Resultado, Servicio, TipoServicio


def _datos_iniciales(equipo):
    """Un renglón por cada punto activo de la ficha, con su EMP (copiado en el servicio, RN-06)."""
    return list(equipo.puntos.filter(activo=True).order_by("orden", "valor_nominal"))


def _pantalla(request, form, formset, equipo, servicio=None, patrones=None):
    return render(request, "servicios/form.html", {
        "form": form, "formset": formset, "equipo": equipo, "servicio": servicio, "patrones": patrones,
        "puntos_ficha": _datos_iniciales(equipo) if servicio is None else None,
        "ia": ia.disponible() and servicio is None, "ia_hojas": settings.IA_MAXIMO_HOJAS,
    })


FILAS_PATRONES = 3


@require_POST
@rol_requerido(*EDITORES)
def leer_certificado(request):
    """Lee el certificado con IA y devuelve los datos para completar el formulario (no guarda el servicio)."""
    equipo = get_object_or_404(equipos_visibles(request.user, Equipo.objects.exclude(estado=EstadoEquipo.BAJA)),
                               pk=request.GET.get("equipo") or 0)
    archivo = request.FILES.get("certificado")
    if archivo is None:
        return JsonResponse({"error": "Primero elige el archivo del certificado."}, status=400)
    try:
        datos = ia.leer_certificado(archivo, equipo, _datos_iniciales(equipo), request.user)
    except ia.ErrorLectura as e:
        return JsonResponse({"error": str(e)}, status=400)
    if len(datos["patrones"]) > FILAS_PATRONES:
        datos["avisos"].append(f"El certificado tiene {len(datos['patrones'])} patrones; se cargaron los primeros "
                               f"{FILAS_PATRONES}. Agrega el resto al corregir el servicio.")
        datos["patrones"] = datos["patrones"][:FILAS_PATRONES]
    return JsonResponse(datos)


@rol_requerido(*SOLO_ADMIN)
def lecturas_ia(request):
    """Registro de lecturas con IA y su costo, para controlar el gasto."""
    qs = LecturaIA.objects.select_related("usuario", "equipo")
    hoy = timezone.localdate()
    del_mes = qs.filter(creado__year=hoy.year, creado__month=hoy.month)
    return render(request, "servicios/lecturas_ia.html", {
        "pagina": Paginator(qs, 30).get_page(request.GET.get("page")),
        "total": qs.aggregate(n=Count("id"), costo=Sum("costo_usd")),
        "mes": del_mes.aggregate(n=Count("id"), costo=Sum("costo_usd")),
        "activa": ia.disponible(), "modelo": settings.IA_MODELO,
    })


def _guardar_patrones(formset, servicio, motivo=""):
    for p in formset.save(commit=False):
        p.servicio = servicio
        if motivo:
            p._change_reason = motivo
        p.save()


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
        elegir = ElegirEquipoForm(request.GET or None, usuario=request.user)
        return render(request, "core/form.html", {
            "form": elegir, "titulo": "Registrar un servicio", "subtitulo": "Elige el equipo que recibió el servicio.",
            "migas": [("Servicios", reverse("servicios:lista"))], "boton": "Continuar", "metodo_get": True,
            "volver": reverse("servicios:lista"),
        })
    equipo = get_object_or_404(equipos_visibles(request.user, Equipo.objects.exclude(estado=EstadoEquipo.BAJA)),
                               pk=equipo_id)
    puntos = _datos_iniciales(equipo)
    form = ServicioForm(request.POST or None, request.FILES or None, equipo=equipo,
                        initial={"fecha": timezone.localdate()})
    PuntosAlta = inlineformset_factory(Servicio, PuntoMedido, form=PuntoMedidoForm, formset=PuntosMedidosFormSet,
                                       extra=len(puntos), can_delete=False)
    formset = PuntosAlta(request.POST or None, instance=Servicio(), prefix="puntos",
                         initial=[{"valor_referencia": f"{p.valor_nominal.normalize():f}"} for p in puntos])
    patrones = patrones_formset(FILAS_PATRONES)(request.POST or None, instance=Servicio(), prefix="patrones")
    if request.method == "POST" and form.is_valid() and patrones.is_valid():
        es_cal = form.cleaned_data["tipo"] == TipoServicio.CALIBRACION
        if es_cal and not puntos:
            form.add_error(None, "El equipo no tiene puntos a calibrar con su EMP. Agrégalos en la ficha del equipo.")
        elif not es_cal or formset.is_valid():
            try:
                with transaction.atomic():
                    servicio = form.save(commit=False)
                    servicio.equipo, servicio.registrado_por = equipo, request.user
                    servicio.save()
                    _guardar_patrones(patrones, servicio)
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
    return _pantalla(request, form, formset, equipo, patrones=patrones)


@rol_requerido(*EDITORES)
def corregir(request, pk):
    """RF-24: la corrección crea una versión nueva y conserva la anterior con fecha, usuario y motivo."""
    servicio = get_object_or_404(del_usuario(request.user, Servicio.objects.select_related("equipo")), pk=pk)
    form = ServicioForm(request.POST or None, request.FILES or None, instance=servicio, equipo=servicio.equipo)
    formset = PuntosFormSet(request.POST or None, instance=servicio, prefix="puntos")
    patrones = patrones_formset(1)(request.POST or None, instance=servicio, prefix="patrones")
    if (request.method == "POST" and form.is_valid() and patrones.is_valid()
            and (not servicio.es_calibracion or formset.is_valid())):
        try:
            with transaction.atomic():
                motivo = form.cleaned_data["motivo"]
                servicio = form.save()
                _guardar_patrones(patrones, servicio, motivo)
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
    return _pantalla(request, form, formset, servicio.equipo, servicio, patrones)


@login_required
def detalle(request, pk):
    s = get_object_or_404(del_usuario(request.user, Servicio.objects.select_related(
        "equipo__unidad", "proveedor", "registrado_por")), pk=pk)
    return render(request, "servicios/detalle.html", {
        "s": s, "puntos": s.puntos.all(), "versiones": s.versiones()[:30],
        "decision": getattr(s, "decision", None), "evaluacion": getattr(s, "evaluacion", None),
        "anterior": s.ultima_conforme_anterior() if s.resultado == Resultado.NO_CONFORME else None,
        "no_cumplen": s.puntos.filter(cumple=False).count(),
    })


@rol_requerido(*EDITORES)
def decision(request, pk):
    """RN-05 / RF-22: proponer «fuera de servicio», pedir confirmación y registrar quién decidió."""
    s = get_object_or_404(del_usuario(request.user, Servicio.objects.select_related("equipo")), pk=pk,
                          tipo=TipoServicio.CALIBRACION,
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
    qs = del_usuario(request.user, Servicio.objects.select_related("equipo", "proveedor"))
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


# --- Archivo de certificados y consulta por QR -----------------------------------------------------------

def _es_imagen(nombre):
    return nombre.rsplit(".", 1)[-1].lower() in ("jpg", "jpeg", "png", "webp")


@login_required
def certificado(request, pk):
    """El certificado archivado, listo para verlo en el teléfono al escanear su QR."""
    s = get_object_or_404(del_usuario(request.user, Servicio.objects.select_related(
        "equipo__unidad", "equipo__marca", "proveedor", "registrado_por")), pk=pk)
    archivos = []
    if s.certificado:
        archivos.append({"titulo": "Certificado", "nombre": s.certificado.name, "imagen": _es_imagen(s.certificado.name)})
    for a in s.anexos.all():
        archivos.append({"titulo": a.titulo, "nombre": a.archivo.name, "imagen": _es_imagen(a.archivo.name)})
    url = url_publica_certificado(s)
    form = AnexoForm() if request.user.puede_editar else None
    return render(request, "servicios/certificado.html", {
        "s": s, "archivos": archivos, "patrones": s.patrones.all(), "qr": qr_svg(url), "url": url, "form": form,
        "vigente": s == Servicio.objects.filter(equipo=s.equipo, tipo=s.tipo).order_by("-fecha", "-pk").first(),
    })


@rol_requerido(*EDITORES)
def anexo(request, pk):
    s = get_object_or_404(del_usuario(request.user, Servicio.objects.all()), pk=pk)
    form = AnexoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        a = form.save(commit=False)
        a.servicio, a.subido_por = s, request.user
        a.save()
        messages.success(request, f"Se agregó «{a.titulo}» al certificado {s.numero_certificado}.")
        return redirect("servicios:certificado", pk=s.pk)
    return render(request, "core/form.html", {
        "form": form, "titulo": f"Agregar una página al certificado {s.numero_certificado}",
        "subtitulo": "Por ejemplo, la foto o el PDF de otra hoja del certificado.",
        "migas": [("Certificados", reverse("servicios:certificados")),
                  (s.numero_certificado, reverse("servicios:certificado", args=[s.pk]))],
        "volver": reverse("servicios:certificado", args=[s.pk]), "boton": "Agregar",
    })


@login_required
def certificados(request):
    """Archivo de certificados: buscar, ver y descargar todos juntos para una auditoría."""
    g = request.GET
    f = {k: g.get(k, "").strip() for k in ("q", "tipo", "proveedor", "anio", "vigentes")}
    qs = del_usuario(request.user, Servicio.objects.select_related("equipo", "proveedor").prefetch_related("anexos"))
    if f["q"]:
        qs = qs.filter(Q(equipo__codigo__icontains=f["q"]) | Q(equipo__descripcion__icontains=f["q"]) |
                       Q(numero_certificado__icontains=f["q"]) | Q(patrones__identificacion__icontains=f["q"]) |
                       Q(patrones__certificado__icontains=f["q"])).distinct()
    if f["tipo"] in TipoServicio.values:
        qs = qs.filter(tipo=f["tipo"])
    if f["proveedor"].isdigit():
        qs = qs.filter(proveedor_id=f["proveedor"])
    if f["anio"].isdigit():
        qs = qs.filter(fecha__year=int(f["anio"]))
    if f["vigentes"] == "1":
        # El último certificado de cada equipo y tipo de servicio
        ultimos = Servicio.objects.filter(equipo=OuterRef("equipo"), tipo=OuterRef("tipo")).order_by("-fecha", "-pk")
        qs = qs.filter(pk=Subquery(ultimos.values("pk")[:1]))
    if g.get("formato") == "zip":
        return _zip_certificados(qs)
    pagina = Paginator(qs, 25).get_page(g.get("page"))
    consulta = g.copy()
    consulta.pop("page", None)
    anios = del_usuario(request.user, Servicio.objects.all()).dates("fecha", "year", order="DESC")
    return render(request, "servicios/certificados.html", {
        "pagina": pagina, "f": f, "consulta": consulta.urlencode(), "tipos": TipoServicio.choices,
        "proveedores": Proveedor.objects.all(), "anios": [d.year for d in anios],
    })


def _zip_certificados(qs):
    """Todos los archivos de los certificados filtrados en un ZIP, ordenados por equipo."""
    import zipfile
    from io import BytesIO
    from pathlib import Path

    buf = BytesIO()
    usados = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for s in qs:
            archivos = ([s.certificado] if s.certificado else []) + [a.archivo for a in s.anexos.all()]
            for i, archivo in enumerate(archivos):
                try:
                    with archivo.open("rb") as fh:
                        datos = fh.read()
                except FileNotFoundError:
                    continue
                ext = Path(archivo.name).suffix
                nombre = f"{s.equipo.codigo}/{s.fecha:%Y-%m-%d}_{s.numero_certificado}" + (f"_{i}" if i else "") + ext
                nombre = nombre.replace(" ", "_")
                if nombre in usados:
                    nombre = nombre.replace(ext, f"_{s.pk}{ext}")
                usados.add(nombre)
                z.writestr(nombre, datos)
    r = HttpResponse(buf.getvalue(), content_type="application/zip")
    r["Content-Disposition"] = f'attachment; filename="certificados_{timezone.localdate():%Y-%m-%d}.zip"'
    return r
