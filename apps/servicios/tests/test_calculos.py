"""RNF-11: los cálculos coinciden con el cálculo hecho a mano, incluidos los casos límite."""
from datetime import date
from decimal import Decimal as D

import pytest

from apps.servicios import calculos as c
from apps.servicios.calculos import Estado, Regla


def evaluar(errores, emp="0.5", u=None, regla=Regla.SIMPLE):
    return c.es_apto(c.evaluar_punto(referencia=D("100"), informado=D(e), incertidumbre=u, emp_tipo="fijo",
                                     emp_valor=D(emp), regla=regla) for e in errores)


def test_ejemplo_balanza_es_apto():
    # EMP ±0,50 g; errores +0,20 / −0,30 / +0,40 → todos cumplen → apto
    assert evaluar(["0.20", "-0.30", "0.40"]) is True


def test_ejemplo_balanza_con_incertidumbre_no_es_apto():
    # Con U = 0,20 g: 0,40 + 0,20 = 0,60 > 0,50 → no apto
    assert evaluar(["0.20", "-0.30", "0.40"], u=D("0.20"), regla=Regla.INCERTIDUMBRE) is False


def test_error_igual_al_emp_cumple():
    assert c.cumple(D("0.5"), D("0.5")) is True
    assert c.cumple(D("-0.5"), D("0.5")) is True
    assert c.cumple(D("0.500001"), D("0.5")) is False


def test_error_mas_incertidumbre_igual_al_emp_cumple():
    assert c.cumple(D("0.3"), D("0.5"), Regla.INCERTIDUMBRE, D("0.2")) is True


def test_un_solo_punto_fuera_hace_no_apto():
    assert evaluar(["0.1", "0.6", "0.1"]) is False


@pytest.mark.parametrize("tipo, valor, ref, alcance, esperado", [
    ("fijo", "0.5", "100", None, "0.5"),
    ("pct_lectura", "1", "250", None, "2.5"),
    ("pct_lectura", "1", "-250", None, "2.5"),
    ("pct_alcance", "1", "2", "10", "0.1"),
])
def test_emp_aplicado(tipo, valor, ref, alcance, esperado):
    assert c.emp_aplicado(tipo, D(valor), D(ref), D(alcance) if alcance else None) == D(esperado)


def test_emp_pct_alcance_sin_alcance_avisa():
    with pytest.raises(c.DatoFaltante):
        c.emp_aplicado("pct_alcance", D("1"), D("2"), None)


def test_error_leido_menos_referencia_o_informado():
    assert c.error_del_punto(D("100"), leido=D("100.2")) == D("0.2")
    assert c.error_del_punto(D("100"), leido=D("100.2"), informado=D("-0.1")) == D("-0.1")
    with pytest.raises(c.DatoFaltante):
        c.error_del_punto(D("100"))


def test_sin_puntos_no_hay_dictamen():
    with pytest.raises(c.DatoFaltante):
        c.es_apto([])


@pytest.mark.parametrize("fecha, meses, esperado", [
    (date(2026, 3, 9), 12, date(2027, 3, 9)),
    (date(2026, 1, 31), 1, date(2026, 2, 28)),
    (date(2027, 12, 31), 2, date(2028, 2, 29)),
    (date(2026, 8, 26), 6, date(2027, 2, 26)),
])
def test_proxima_fecha(fecha, meses, esperado):
    assert c.proxima_fecha(fecha, meses) == esperado


HOY = date(2026, 10, 15)


@pytest.mark.parametrize("proxima, esperado", [
    (date(2026, 10, 14), Estado.VENCIDO),
    (date(2026, 10, 15), Estado.POR_VENCER),   # vence hoy: todavía no está vencido
    (date(2026, 11, 14), Estado.POR_VENCER),   # aviso en el día exacto (30 días)
    (date(2026, 11, 15), Estado.VIGENTE),
    (None, Estado.VENCIDO),                    # calibrado, pero nunca conforme
])
def test_estado_de_calibracion(proxima, esperado):
    assert c.estado_calibracion(proxima, HOY, 30) == esperado


def test_sin_calibraciones_es_sin_registro():
    assert c.estado_calibracion(None, HOY, 30, tiene_calibraciones=False) == Estado.SIN_REGISTRO
