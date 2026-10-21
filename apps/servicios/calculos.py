"""
Reglas de cálculo del sistema (RN-02, RN-03, RN-04).

Son funciones puras: con los mismos datos dan siempre el mismo resultado (RNF-11) y se
prueban sin base de datos. Todo se calcula con Decimal para no arrastrar errores de redondeo.
"""
import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

CIEN = Decimal("100")


class Regla:
    SIMPLE = "simple"
    INCERTIDUMBRE = "incertidumbre"


class Estado:
    """Estado de calibración (RN-03). Se calcula, nunca se guarda."""

    SIN_REGISTRO = "sin_registro"
    VENCIDO = "vencido"
    POR_VENCER = "por_vencer"
    VIGENTE = "vigente"

    ETIQUETAS = {SIN_REGISTRO: "Sin registro", VENCIDO: "Vencido", POR_VENCER: "Por vencer", VIGENTE: "Vigente"}
    ORDEN = [VIGENTE, POR_VENCER, VENCIDO, SIN_REGISTRO]


class DatoFaltante(ValueError):
    pass


def emp_aplicado(tipo, valor, referencia, alcance=None):
    """RF-07: EMP en unidades del equipo para un punto dado."""
    valor = Decimal(valor)
    if tipo == "fijo":
        return abs(valor)
    if tipo == "pct_lectura":
        return abs(valor) * abs(Decimal(referencia)) / CIEN
    if tipo == "pct_alcance":
        if alcance in (None, ""):
            raise DatoFaltante("El EMP es un % del alcance, pero el equipo no tiene cargada su capacidad o alcance.")
        return abs(valor) * abs(Decimal(alcance)) / CIEN
    raise ValueError(f"Tipo de EMP desconocido: {tipo}")


def error_del_punto(referencia, leido=None, informado=None):
    """Error = valor que marcó el equipo − valor de referencia, o el error que informa el certificado."""
    if informado not in (None, ""):
        return Decimal(informado)
    if leido in (None, "") or referencia in (None, ""):
        raise DatoFaltante("Falta el valor que marcó el equipo o el error que informa el certificado.")
    return Decimal(leido) - Decimal(referencia)


def cumple(error, emp, regla=Regla.SIMPLE, incertidumbre=None):
    """RN-04: el punto cumple si el error no supera el EMP. Con la regla con incertidumbre se suma U antes de comparar."""
    magnitud = abs(Decimal(error))
    if regla == Regla.INCERTIDUMBRE:
        magnitud += abs(Decimal(incertidumbre or 0))
    return magnitud <= Decimal(emp)


@dataclass
class ResultadoPunto:
    error: Decimal
    emp: Decimal
    cumple: bool


def evaluar_punto(*, referencia, leido=None, informado=None, incertidumbre=None, emp_tipo, emp_valor,
                  alcance=None, regla=Regla.SIMPLE):
    error = error_del_punto(referencia, leido, informado)
    emp = emp_aplicado(emp_tipo, emp_valor, referencia, alcance)
    return ResultadoPunto(error=error, emp=emp, cumple=cumple(error, emp, regla, incertidumbre))


def es_apto(resultados):
    """RN-04: apto solo si todos los puntos cumplen. Sin puntos no hay dictamen."""
    resultados = list(resultados)
    if not resultados:
        raise DatoFaltante("Una calibración necesita al menos un punto medido.")
    return all(r.cumple for r in resultados)


def sumar_meses(fecha, meses):
    """Suma meses de calendario; si el día no existe (31 de abril), usa el último día del mes."""
    total = fecha.month - 1 + meses
    anio, mes = fecha.year + total // 12, total % 12 + 1
    return date(anio, mes, min(fecha.day, calendar.monthrange(anio, mes)[1]))


def proxima_fecha(fecha_conforme, intervalo_meses):
    """RN-02: fecha de la última calibración conforme + intervalo del equipo."""
    return sumar_meses(fecha_conforme, intervalo_meses)


def estado_calibracion(proxima, hoy, plazo_aviso_dias, tiene_calibraciones=True):
    """
    RN-03. «Sin registro» si nunca fue calibrado. Si fue calibrado pero ninguna calibración
    fue conforme, no tiene fecha válida y cuenta como vencido.
    """
    if not tiene_calibraciones:
        return Estado.SIN_REGISTRO
    if proxima is None:
        return Estado.VENCIDO
    dias = (proxima - hoy).days
    if dias < 0:
        return Estado.VENCIDO
    if dias <= plazo_aviso_dias:
        return Estado.POR_VENCER
    return Estado.VIGENTE
