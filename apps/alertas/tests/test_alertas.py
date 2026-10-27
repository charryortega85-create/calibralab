from datetime import date, timedelta

from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.alertas import avisos
from apps.alertas.estado import con_estado, conteo, prioridades
from apps.alertas.models import Aviso, ResultadoEnvio, TipoAviso
from apps.equipos.models import Equipo, EstadoEquipo
from apps.servicios.calculos import Estado


def estado_de(equipo, dia=None):
    return con_estado(Equipo.objects.filter(pk=equipo.pk), dia=dia, plazo=30).get().estado_cal


def test_estado_segun_la_ultima_calibracion(crear_equipo, calibrar):
    e = crear_equipo()
    assert estado_de(e) == Estado.SIN_REGISTRO
    calibrar(e, date(2025, 10, 15))                         # vence el 2026-10-15
    assert estado_de(e, date(2026, 10, 15)) == Estado.POR_VENCER
    assert estado_de(e, date(2026, 10, 16)) == Estado.VENCIDO
    assert estado_de(e, date(2026, 9, 15)) == Estado.POR_VENCER
    assert estado_de(e, date(2026, 9, 14)) == Estado.VIGENTE
    s = calibrar(e, date(2026, 10, 10), resultado="no_conforme")  # el resultado no cambia el estado
    assert s.proxima_fecha == date(2027, 10, 10)
    anotado = con_estado(Equipo.objects.filter(pk=e.pk), dia=date(2026, 10, 15), plazo=30).get()
    assert anotado.estado_cal == Estado.VIGENTE and anotado.ultimo_resultado == "no_conforme"


def test_calibracion_sin_resultado_cuenta_por_su_fecha(crear_equipo, calibrar):
    e = crear_equipo()
    calibrar(e, date(2026, 10, 1), resultado="")
    assert estado_de(e, date(2026, 10, 2)) == Estado.VIGENTE


def test_aviso_tambien_para_la_ultima_no_conforme(crear_equipo, calibrar):
    e = crear_equipo()
    calibrar(e, date(2024, 1, 1), resultado="no_conforme")
    assert (e, TipoAviso.VENCIDO) in avisos.pendientes()


def test_prioridad_vencidos_primero_y_por_criticidad(crear_equipo, calibrar):
    hoy = timezone.localdate()
    a = crear_equipo("EQ-A", criticidad="baja")
    b = crear_equipo("EQ-B", criticidad="alta")
    c = crear_equipo("EQ-C", criticidad="alta")
    calibrar(a, hoy.replace(year=hoy.year - 1) - timedelta(days=5))
    calibrar(b, hoy.replace(year=hoy.year - 1) - timedelta(days=5))
    calibrar(c, hoy.replace(year=hoy.year - 1) + timedelta(days=5))
    assert [p.equipo.codigo for p in prioridades()] == ["EQ-B", "EQ-A", "EQ-C"]
    assert conteo()[Estado.VENCIDO] == 2


def test_avisos_se_envian_una_vez_y_se_cierran_con_una_calibracion_nueva(crear_equipo, calibrar, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    hoy = timezone.localdate()
    e = crear_equipo()
    calibrar(e, hoy.replace(year=hoy.year - 1) + timedelta(days=10))
    enviados = avisos.enviar_pendientes()
    assert [(a.equipo, a.tipo, a.resultado) for a in enviados] == [(e, TipoAviso.POR_VENCER, ResultadoEnvio.ENVIADO)]
    assert len(mail.outbox) == 1 and e.codigo in mail.outbox[0].subject
    assert avisos.pendientes() == []                       # no se repite
    calibrar(e, hoy)
    assert avisos.pendientes() == []                       # la calibración nueva cierra el aviso


def test_equipos_de_baja_no_se_avisan(crear_equipo, calibrar):
    e = crear_equipo(estado=EstadoEquipo.BAJA)
    calibrar(e, date(2024, 1, 1))
    assert avisos.pendientes() == []


def test_error_de_envio_queda_registrado_y_se_reintenta(crear_equipo, calibrar, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST, settings.EMAIL_PORT = "127.0.0.1", 1
    e = crear_equipo()
    calibrar(e, date(2024, 1, 1))
    a = avisos.enviar_pendientes()[0]
    assert a.resultado == ResultadoEnvio.ERROR and a.detalle
    assert [(x.pk, tipo) for x, tipo in avisos.pendientes()] == [(e.pk, TipoAviso.VENCIDO)]


def test_pantallas_de_estado_y_avisos(cliente_de, consulta, admin, crear_equipo, calibrar, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    calibrar(crear_equipo(), date(2024, 1, 1))
    c = cliente_de(consulta)
    assert "EQ-0001" in c.get(reverse("alertas:estado")).content.decode()
    assert c.post(reverse("alertas:enviar")).status_code == 403
    cliente_de(admin).post(reverse("alertas:enviar"))
    assert Aviso.objects.count() == 1
    assert "EQ-0001" in c.get(reverse("alertas:avisos")).content.decode()
