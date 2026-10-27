"""
RF-28: avisos por correo a los responsables.

Un aviso cuando el equipo entra en el plazo de aviso y otro cuando vence. Cada aviso
queda atado a la próxima fecha que lo originó: al registrar una calibración nueva la
fecha cambia y se deja de avisar; los equipos de baja no se avisan.
"""
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from apps.servicios.calculos import Estado

from .estado import activos, hoy
from .models import Aviso, ResultadoEnvio, TipoAviso

TIPO_POR_ESTADO = {Estado.POR_VENCER: TipoAviso.POR_VENCER, Estado.VENCIDO: TipoAviso.VENCIDO}


def pendientes(dia=None):
    """Equipos que hoy necesitan un aviso que todavía no se envió bien."""
    dia = dia or hoy()
    resultado = []
    for e in activos(dia=dia).filter(estado_cal__in=list(TIPO_POR_ESTADO)).select_related("responsable"):
        if e.proxima is None:
            continue  # sin fecha de próxima calibración: no hay vencimiento que avisar
        tipo = TIPO_POR_ESTADO[e.estado_cal]
        ya = Aviso.objects.filter(equipo=e, tipo=tipo, proxima_fecha=e.proxima, resultado=ResultadoEnvio.ENVIADO)
        if not ya.exists():
            resultado.append((e, tipo))
    return resultado


def enviar(equipo, tipo, dia=None):
    dia = dia or hoy()
    destinatario = equipo.responsable
    contexto = {"e": equipo, "tipo": tipo, "dias": (equipo.proxima - dia).days,
                "url": settings.URL_SISTEMA.rstrip("/") + equipo.get_absolute_url()}
    asunto = (f"[CalibraLab] {equipo.codigo}: la calibración vence el {equipo.proxima:%Y-%m-%d}"
              if tipo == TipoAviso.POR_VENCER else f"[CalibraLab] {equipo.codigo}: calibración VENCIDA")
    aviso = Aviso(equipo=equipo, tipo=tipo, proxima_fecha=equipo.proxima, destinatario=destinatario,
                  correo=destinatario.email)
    try:
        send_mail(asunto, render_to_string("alertas/correo.txt", contexto), None, [destinatario.email])
        aviso.resultado = ResultadoEnvio.ENVIADO
    except Exception as exc:  # el error queda registrado y el aviso se reintenta al día siguiente
        aviso.resultado, aviso.detalle = ResultadoEnvio.ERROR, str(exc)[:250]
    aviso.save()
    return aviso


def enviar_pendientes(dia=None):
    return [enviar(e, tipo, dia) for e, tipo in pendientes(dia)]
