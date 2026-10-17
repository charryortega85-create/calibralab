"""
Consulta pública por QR: al escanear la etiqueta del equipo o el QR de un certificado se ven sus
datos sin iniciar sesión. Solo lectura, y solo del registro cuyo código firmado lleva el QR.
"""
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin

from apps.alertas.estado import con_estado
from apps.equipos.models import Equipo
from apps.servicios.models import Servicio, TipoServicio

from .qr import firmar, leer


def _es_imagen(nombre):
    return nombre.rsplit(".", 1)[-1].lower() in ("jpg", "jpeg", "png", "webp")


def _pk(tipo, token):
    pk = leer(tipo, token)
    if pk is None:
        raise Http404
    return pk


def _ultimos_por_tipo(equipo):
    """El último servicio de cada tipo (calibración, calificación, verificación)."""
    ultimos = {}
    for s in equipo.servicios.select_related("proveedor").order_by("-fecha", "-pk"):
        ultimos.setdefault(s.tipo, s)
    return [ultimos[t] for t in TipoServicio.values if t in ultimos]


def qr_equipo(request, token):
    equipo = get_object_or_404(con_estado(Equipo.objects.select_related("marca", "ubicacion", "unidad")),
                               pk=_pk("equipo", token))
    ultimos = _ultimos_por_tipo(equipo)
    historial = equipo.servicios.select_related("proveedor").order_by("-fecha", "-pk")[:10]
    hoy = timezone.localdate()
    return render(request, "publico/equipo.html", {
        "e": equipo, "ultimos": [(s, firmar("certificado", s.pk)) for s in ultimos],
        "historial": [(s, firmar("certificado", s.pk)) for s in historial], "hoy": hoy,
        "dias": (equipo.proxima - hoy).days if equipo.proxima else None,
    })


def _archivos(s):
    archivos = []
    if s.certificado:
        archivos.append(("Certificado", s.certificado.name))
    archivos += [(a.titulo, a.archivo.name) for a in s.anexos.all()]
    return archivos


def qr_certificado(request, token):
    s = get_object_or_404(Servicio.objects.select_related("equipo__unidad", "equipo__marca", "proveedor"),
                          pk=_pk("certificado", token))
    archivos = [{"titulo": t, "n": i, "imagen": _es_imagen(n), "pdf": n.lower().endswith(".pdf")}
                for i, (t, n) in enumerate(_archivos(s))]
    ultimo = Servicio.objects.filter(equipo=s.equipo, tipo=s.tipo).order_by("-fecha", "-pk").first()
    return render(request, "publico/certificado.html", {
        "s": s, "token": token, "archivos": archivos, "patrones": s.patrones.all(),
        "puntos": s.puntos.all() if s.es_calibracion else [], "vigente": s == ultimo,
        "token_equipo": firmar("equipo", s.equipo_id),
    })


@xframe_options_sameorigin
def qr_archivo(request, token, n):
    """Los archivos del certificado escaneado; ningún otro archivo del sistema."""
    s = get_object_or_404(Servicio, pk=_pk("certificado", token))
    archivos = _archivos(s)
    if not 0 <= n < len(archivos):
        raise Http404
    raiz = Path(settings.MEDIA_ROOT).resolve()
    destino = (raiz / archivos[n][1]).resolve()
    if raiz not in destino.parents or not destino.is_file():
        raise Http404
    return FileResponse(open(destino, "rb"), filename=destino.name)
