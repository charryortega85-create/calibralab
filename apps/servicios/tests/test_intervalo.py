"""Sugerencia del intervalo de calibración según el uso de la tolerancia y la deriva."""
from datetime import date
from decimal import Decimal as D

from django.urls import reverse

from apps.servicios.intervalo import Calibracion, sugerir, sugerencia_para


def cal(anio, uso, apta=True):
    return Calibracion(date(anio, 3, 1), apta, D(uso))


def test_sin_calibraciones():
    assert sugerir([], 12).cambio == "sin_datos"


def test_no_apta_acorta_a_la_mitad():
    s = sugerir([cal(2024, "0.3"), cal(2025, "1.2", apta=False)], 12)
    assert (s.cambio, s.meses) == ("acortar", 6)


def test_cerca_del_limite_acorta():
    s = sugerir([cal(2024, "0.5"), cal(2025, "0.85")], 12)
    assert (s.cambio, s.meses) == ("acortar", 9) and s.uso_pct == 85


def test_estable_y_holgado_alarga_hasta_un_50_por_ciento():
    s = sugerir([cal(2023, "0.20"), cal(2024, "0.18"), cal(2025, "0.20")], 12)
    assert (s.cambio, s.meses) == ("alargar", 18)


def test_deriva_que_llega_al_limite_antes_acorta():
    # Sube 30 puntos por año y ya usa el 70 %: llegaría al 80 % en unos 4 meses → acorta, como mucho a la mitad
    s = sugerir([cal(2023, "0.10"), cal(2024, "0.40"), cal(2025, "0.70")], 12)
    assert (s.cambio, s.meses) == ("acortar", 6) and s.deriva_pct == 30


def test_con_deriva_lenta_no_alarga():
    s = sugerir([cal(2023, "0.10"), cal(2024, "0.30"), cal(2025, "0.55")], 12)
    assert (s.cambio, s.meses) == ("mantener", 12)


def test_una_sola_calibracion_mantiene():
    assert sugerir([cal(2025, "0.3")], 12).cambio == "mantener"


def test_nunca_baja_de_3_ni_pasa_de_36_meses():
    assert sugerir([cal(2025, "2", apta=False)], 4).meses == 3
    assert sugerir([cal(2023, "0.1"), cal(2025, "0.1")], 30).meses == 36


def test_con_datos_guardados_y_en_la_ficha(cliente_de, tecnico, crear_equipo, calibrar):
    e = crear_equipo()  # EMP ±0,5 en cada punto
    calibrar(e, date(2024, 3, 1), errores=("0.05", "0.05", "0.05"), numero="CC-1")
    calibrar(e, date(2025, 3, 1), errores=("0.05", "-0.05", "0.05"), numero="CC-2")
    s = sugerencia_para(e)
    assert s.uso_pct == 10 and (s.cambio, s.meses) == ("alargar", 18)
    html = cliente_de(tecnico).get(e.get_absolute_url()).content.decode()
    assert "Sugerido: 18 meses" in html
    r = cliente_de(tecnico).get(reverse("reportes:intervalos")).content.decode()
    assert e.codigo in r and "Alargar" in r
