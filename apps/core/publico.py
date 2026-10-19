"""
Consulta pública por QR: al escanear la etiqueta del equipo se ve su historial, y al escanear el
QR de un certificado se puede leer el certificado. Sin iniciar sesión, solo lectura, solo del
registro cuyo código firmado lleva el QR, y sin descargar los archivos (ver visor.py).
"""
from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.alertas.estado import con_estado
from apps.equipos.models import Equipo
from apps.servicios.models import Servicio

from . import visor
from .qr import firmar, leer

HISTORIAL = 30


def _pk(tipo, token):
    pk = leer(tipo, token)
    if pk is None:
        raise Http404
    return pk


def qr_equipo(request, token):
    """Estado del equipo y su historial de servicios, cada uno con su certificado."""
    equipo = get_object_or_404(con_estado(Equipo.objects.select_related("marca")), pk=_pk("equipo", token))
    historial = equipo.servicios.select_related("proveedor").order_by("-fecha", "-pk")[:HISTORIAL]
    hoy = timezone.localdate()
    return _sin_cache(render(request, "publico/equipo.html", {
        "e": equipo, "historial": [(s, firmar("certificado", s.pk)) for s in historial], "hoy": hoy,
        "dias": (equipo.proxima - hoy).days if equipo.proxima else None,
    }))


def _archivos(s):
    """Las rutas en disco de los archivos del certificado que se pueden mostrar como hojas."""
    raiz = Path(settings.MEDIA_ROOT).resolve()
    nombres = ([s.certificado.name] if s.certificado else []) + [a.archivo.name for a in s.anexos.all()]
    rutas = []
    for nombre in nombres:
        ruta = (raiz / nombre).resolve()
        if raiz in ruta.parents and ruta.is_file() and visor.visible(ruta):
            rutas.append(ruta)
    return rutas


def qr_certificado(request, token):
    """El certificado para leerlo en pantalla: hojas como imágenes, sin enlace para descargar."""
    s = get_object_or_404(Servicio.objects.select_related("equipo", "proveedor"), pk=_pk("certificado", token))
    hojas = [(n, p) for n, ruta in enumerate(_archivos(s)) for p in range(visor.contar_paginas(ruta))]
    ultimo = Servicio.objects.filter(equipo=s.equipo, tipo=s.tipo).order_by("-fecha", "-pk").first()
    return _sin_cache(render(request, "publico/certificado.html", {
        "s": s, "token": token, "hojas": hojas, "vigente": s == ultimo,
        "token_equipo": firmar("equipo", s.equipo_id),
    }))


def qr_hoja(request, token, n, p):
    """Una hoja del certificado escaneado, como imagen con marca de agua. Nunca el archivo original."""
    if request.headers.get("Sec-Fetch-Dest") == "document":
        raise Http404  # se pide desde el visor, no abriendo la imagen sola para guardarla
    s = get_object_or_404(Servicio, pk=_pk("certificado", token))
    rutas = _archivos(s)
    if not 0 <= n < len(rutas) or not 0 <= p < visor.contar_paginas(rutas[n]):
        raise Http404
    r = HttpResponse(visor.pagina_jpg(rutas[n], p), content_type="image/jpeg")
    r["Content-Disposition"] = "inline"
    return _sin_cache(r)


def _sin_cache(r):
    r["Cache-Control"] = "no-store, private"
    r["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return r
