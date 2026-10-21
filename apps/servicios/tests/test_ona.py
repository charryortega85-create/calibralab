"""Ajustes pedidos por el ONA (POL003 y CRI008): trazabilidad, incertidumbre y verificación intermedia."""
from datetime import date, timedelta

from django.urls import reverse
from django.utils import timezone

from apps.catalogos.models import Proveedor
from apps.servicios.models import Servicio, TipoServicio

from .test_servicios import datos_calibracion

LECTURAS = [("100", "100.1"), ("500", "500"), ("1000", "1000.2")]


def crear(cliente, equipo, datos):
    return cliente.post(f"{reverse('servicios:crear')}?equipo={equipo.pk}", datos)


def test_proveedor_no_acreditado_pide_justificar(cliente_de, tecnico, crear_equipo):
    e = crear_equipo()
    otro = Proveedor.objects.create(nombre="Taller local")  # reconocimiento «otro»
    c = cliente_de(tecnico)
    r = crear(c, e, datos_calibracion(otro, LECTURAS))
    assert "Justifica la trazabilidad: el proveedor no es un INM" in r.content.decode()
    assert not Servicio.objects.exists()
    crear(c, e, datos_calibracion(otro, LECTURAS, justificacion_trazabilidad="No hay laboratorio acreditado en masa."))
    assert Servicio.objects.get().justificacion_trazabilidad


def test_fuera_de_alcance_o_acreditacion_vencida_pide_justificar(cliente_de, tecnico, crear_equipo, catalogo):
    e = crear_equipo()
    c = cliente_de(tecnico)
    r = crear(c, e, datos_calibracion(catalogo["proveedor"], LECTURAS, fuera_alcance="on"))
    assert "fuera del alcance acreditado" in r.content.decode()
    p = catalogo["proveedor"]
    p.acreditacion_vence = timezone.localdate() - timedelta(days=30)
    p.save()
    r = crear(c, e, datos_calibracion(p, LECTURAS))
    assert "estaba vencida" in r.content.decode() and not Servicio.objects.exists()


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
