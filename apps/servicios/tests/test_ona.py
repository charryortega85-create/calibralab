"""Ajustes pedidos por el ONA (POL003 y CRI008): incertidumbre y verificación intermedia."""
from datetime import date, timedelta

from django.urls import reverse
from django.utils import timezone

from apps.servicios.models import Servicio, TipoServicio


def test_falta_de_incertidumbre_se_avisa(cliente_de, tecnico, crear_equipo, calibrar):
    e = crear_equipo()
    s = calibrar(e, date(2026, 3, 1))
    html = cliente_de(tecnico).get(s.get_absolute_url()).content.decode()
    assert "3 puntos sin incertidumbre (U)" in html
    s2 = calibrar(e, date(2026, 4, 1), incertidumbre="0.05", numero="CC-2")
    assert "sin incertidumbre" not in cliente_de(tecnico).get(s2.get_absolute_url()).content.decode()


def test_verificacion_intermedia_no_pide_vigencia_ni_cambia_la_proxima(cliente_de, tecnico, crear_equipo, catalogo,
                                                                       calibrar):
    e = crear_equipo()
    cal = calibrar(e, date(2026, 3, 1))
    ayer = (timezone.localdate() - timedelta(days=1)).isoformat()
    r = cliente_de(tecnico).post(f"{reverse('servicios:crear')}?equipo={e.pk}", {
        "tipo": "verificacion", "fecha": ayer, "proveedor": catalogo["proveedor"].pk, "numero_certificado": "VI-01",
        "resultado": "conforme", "patrones-TOTAL_FORMS": 0, "patrones-INITIAL_FORMS": 0,
        "puntos-TOTAL_FORMS": 0, "puntos-INITIAL_FORMS": 0})
    v = Servicio.objects.get(tipo=TipoServicio.VERIFICACION)
    assert r.status_code == 302 and v.vigencia_hasta is None
    assert cal.proxima_fecha == Servicio.objects.get(pk=cal.pk).proxima_fecha
    assert cliente_de(tecnico).get(e.get_absolute_url()).status_code == 200
