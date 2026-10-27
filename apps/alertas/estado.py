"""
Estado de calibración de los equipos (RN-02, RN-03), calculado en la base de datos para
poder filtrar y ordenar listados grandes (RNF-21) sin guardarlo nunca.

El estado sale de la fecha de próxima calibración de la última calibración registrada,
sea cual sea el resultado que informó el proveedor.
"""
from dataclasses import dataclass
from datetime import date

from django.db.models import Case, CharField, Exists, OuterRef, Q, Subquery, Value, When
from django.utils import timezone

from apps.cuentas.models import Configuracion
from apps.equipos.models import ORDEN_CRITICIDAD, Equipo, EstadoEquipo
from apps.servicios.calculos import Estado
from apps.servicios.models import Servicio, TipoServicio


def hoy():
    return timezone.localdate()


def con_estado(qs=None, dia=None, plazo=None):
    """Anota cada equipo con `proxima` (fecha), `ultimo_resultado` y `estado_cal` (RN-03)."""
    dia = dia or hoy()
    plazo = Configuracion.actual().plazo_aviso_dias if plazo is None else plazo
    qs = Equipo.objects.all() if qs is None else qs
    calibraciones = Servicio.objects.filter(equipo=OuterRef("pk"), tipo=TipoServicio.CALIBRACION)
    ultima = calibraciones.order_by("-fecha", "-pk")
    limite = date.fromordinal(dia.toordinal() + plazo)
    return qs.annotate(
        tiene_cal=Exists(calibraciones),
        proxima=Subquery(ultima.values("proxima_fecha")[:1]),
        ultimo_resultado=Subquery(ultima.values("resultado")[:1]),
    ).annotate(
        estado_cal=Case(
            When(tiene_cal=False, then=Value(Estado.SIN_REGISTRO)),
            When(Q(proxima__isnull=True) | Q(proxima__lt=dia), then=Value(Estado.VENCIDO)),
            When(proxima__lte=limite, then=Value(Estado.POR_VENCER)),
            default=Value(Estado.VIGENTE),
            output_field=CharField(),
        )
    )


def activos(qs=None, **kw):
    """Equipos que cuentan para alertas: los de baja no se avisan (RF-28)."""
    return con_estado(qs, **kw).exclude(estado=EstadoEquipo.BAJA)


@dataclass
class Prioridad:
    equipo: Equipo
    dias: int | None


def prioridades(qs=None, dia=None, limite=None):
    """
    RF-26 / RF-33: vencidos primero, luego por vencer; dentro de cada grupo, criticidad
    (alta a baja) y después los días que faltan.
    """
    dia = dia or hoy()
    lista = list(activos(qs, dia=dia).filter(estado_cal__in=[Estado.VENCIDO, Estado.POR_VENCER])
                 .select_related("responsable", "ubicacion"))

    def clave(e):
        dias = (e.proxima - dia).days if e.proxima else -10_000
        return (0 if e.estado_cal == Estado.VENCIDO else 1, ORDEN_CRITICIDAD.get(e.criticidad, 9), dias)

    lista.sort(key=clave)
    resultado = [Prioridad(e, (e.proxima - dia).days if e.proxima else None) for e in lista]
    return resultado[:limite] if limite else resultado


def conteo(qs=None, dia=None):
    datos = {k: 0 for k in Estado.ORDEN}
    for fila in activos(qs, dia=dia).values_list("estado_cal", flat=True):
        datos[fila] += 1
    return datos
