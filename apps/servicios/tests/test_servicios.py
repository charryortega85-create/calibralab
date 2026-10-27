from datetime import date, timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.core.modelos import BorradoNoPermitido
from apps.equipos.models import EstadoEquipo
from apps.servicios.models import DecisionNoApto, Resultado, Servicio, TipoServicio


def pdf():
    return SimpleUploadedFile("cert.pdf", b"%PDF-1.4 prueba", content_type="application/pdf")


def datos_calibracion(proveedor, **extra):
    datos = {"fecha": (timezone.localdate() - timedelta(days=1)).isoformat(), "proveedor": proveedor.pk,
             "numero_certificado": "CC-2026-0001", "certificado": pdf(),
             "patrones-TOTAL_FORMS": 0, "patrones-INITIAL_FORMS": 0}
    datos.update(extra)
    return datos


def crear_url(equipo):
    return f"{reverse('servicios:crear')}?equipo={equipo.pk}"


def test_calibracion_calcula_la_proxima_fecha(cliente_de, tecnico, crear_equipo, catalogo):
    e = crear_equipo(puntos=())
    r = cliente_de(tecnico).post(crear_url(e), datos_calibracion(catalogo["proveedor"], resultado="conforme"))
    s = Servicio.objects.get()
    assert r.status_code == 302 and r.url == s.get_absolute_url()
    assert s.resultado == Resultado.CONFORME and s.dictamen == "Conforme"
    ayer = timezone.localdate() - timedelta(days=1)
    assert s.proxima_fecha == s.proxima_fecha_calculada == ayer.replace(year=ayer.year + 1)
    assert not s.puntos.exists()


def test_calibracion_sin_puntos_ni_resultado(cliente_de, tecnico, crear_equipo, catalogo):
    e = crear_equipo(puntos=())
    r = cliente_de(tecnico).post(crear_url(e), datos_calibracion(catalogo["proveedor"]))
    s = Servicio.objects.get()
    assert r.status_code == 302 and s.resultado == "" and s.dictamen == "Sin dictamen"
    assert s.proxima_fecha is not None


def test_no_conforme_avisa_y_no_cambia_el_estado_del_equipo(cliente_de, tecnico, crear_equipo, catalogo):
    e = crear_equipo()
    c = cliente_de(tecnico)
    r = c.post(crear_url(e), datos_calibracion(catalogo["proveedor"], resultado="no_conforme"), follow=True)
    s = Servicio.objects.get()
    assert r.redirect_chain[-1][0] == s.get_absolute_url()
    assert s.resultado == Resultado.NO_CONFORME and s.proxima_fecha is not None
    assert any(m.level_tag == "warning" and "NO CONFORME" in m.message for m in r.context["messages"])
    assert "resultado no conforme" in r.content.decode()
    e.refresh_from_db()
    assert e.estado == EstadoEquipo.EN_SERVICIO


def test_el_registro_muestra_los_puntos_de_la_ficha(cliente_de, tecnico, crear_equipo):
    c = cliente_de(tecnico)
    con_puntos = crear_equipo()
    sin_puntos = crear_equipo("EQ-0002", puntos=())
    assert "Puntos a calibrar definidos para este equipo" in c.get(crear_url(con_puntos)).content.decode()
    assert "Puntos a calibrar definidos para este equipo" not in c.get(crear_url(sin_puntos)).content.decode()


def test_mantener_estado_exige_justificacion(cliente_de, tecnico, crear_equipo, calibrar):
    e = crear_equipo()
    s = calibrar(e, date(2026, 9, 1), resultado="no_conforme")
    r = cliente_de(tecnico).post(reverse("servicios:decision", args=[s.pk]), {"decision": "mantener"})
    assert r.status_code == 200 and not DecisionNoApto.objects.exists()


def test_rn08_calibracion_sin_certificado_se_rechaza(cliente_de, tecnico, crear_equipo, catalogo):
    e = crear_equipo()
    datos = datos_calibracion(catalogo["proveedor"])
    datos.pop("certificado")
    r = cliente_de(tecnico).post(crear_url(e), datos)
    assert r.status_code == 200 and "obligatorio (RN-08)" in r.content.decode()
    assert not Servicio.objects.exists()


def test_fecha_futura_se_rechaza(cliente_de, tecnico, crear_equipo, catalogo):
    e = crear_equipo()
    datos = datos_calibracion(catalogo["proveedor"], fecha=(timezone.localdate() + timedelta(days=1)).isoformat())
    r = cliente_de(tecnico).post(crear_url(e), datos)
    assert "no puede ser futura" in r.content.decode() and not Servicio.objects.exists()


def test_fecha_manual_exige_justificacion(cliente_de, tecnico, crear_equipo, catalogo):
    e = crear_equipo()
    datos = datos_calibracion(catalogo["proveedor"], proxima_manual="2027-01-01")
    r = cliente_de(tecnico).post(crear_url(e), datos)
    assert "justificación" in r.content.decode() and not Servicio.objects.exists()
    datos = datos_calibracion(catalogo["proveedor"], proxima_manual="2027-01-01",
                              justificacion_proxima="Se alinea con la calibración de las otras balanzas")
    cliente_de(tecnico).post(crear_url(e), datos)
    s = Servicio.objects.get()
    assert s.proxima_fecha == date(2027, 1, 1) and s.proxima_fecha != s.proxima_fecha_calculada


def datos_correccion(s, proveedor, **extra):
    datos = {"fecha": s.fecha.isoformat(), "proveedor": proveedor.pk, "numero_certificado": s.numero_certificado,
             "resultado": s.resultado, "motivo": "Error de transcripción del certificado",
             "patrones-TOTAL_FORMS": 0, "patrones-INITIAL_FORMS": 0}
    datos.update(extra)
    return datos


def test_rn07_correccion_conserva_version_y_motivo(cliente_de, tecnico, crear_equipo, calibrar, catalogo):
    s = calibrar(crear_equipo(), date(2026, 3, 9))
    s.certificado = pdf()
    s.save()
    datos = datos_correccion(s, catalogo["proveedor"], numero_certificado="CC-1-BIS", resultado="no_conforme")
    r = cliente_de(tecnico).post(reverse("servicios:corregir", args=[s.pk]), datos)
    assert r.status_code == 302, r.content.decode()[:500]
    s.refresh_from_db()
    assert s.numero_certificado == "CC-1-BIS" and s.resultado == Resultado.NO_CONFORME
    versiones = list(s.versiones())
    assert any(v.numero_certificado == "CC-1" for v in versiones)
    assert any(v.numero_certificado == "CC-1-BIS" for v in versiones)
    assert any(v.history_change_reason == "Error de transcripción del certificado" for v in versiones)


def test_corregir_recalcula_la_proxima_fecha(cliente_de, tecnico, crear_equipo, calibrar, catalogo):
    s = calibrar(crear_equipo(), date(2026, 3, 9))
    s.certificado = pdf()
    s.save()
    r = cliente_de(tecnico).post(reverse("servicios:corregir", args=[s.pk]),
                                 datos_correccion(s, catalogo["proveedor"], fecha="2026-04-01"))
    assert r.status_code == 302
    s.refresh_from_db()
    assert s.proxima_fecha == s.proxima_fecha_calculada == date(2027, 4, 1)


def test_corregir_solo_acepta_calibraciones(cliente_de, tecnico, crear_equipo, catalogo):
    e = crear_equipo()
    s = Servicio.objects.create(equipo=e, tipo=TipoServicio.CALIFICACION, fecha=date(2026, 1, 10),
                                proveedor=catalogo["proveedor"], numero_certificado="CQ-1", resultado="conforme",
                                registrado_por=tecnico)
    assert cliente_de(tecnico).get(reverse("servicios:corregir", args=[s.pk])).status_code == 404


def test_rn07_no_se_borra(crear_equipo, calibrar):
    s = calibrar(crear_equipo(), date(2026, 3, 9))
    with pytest.raises(BorradoNoPermitido):
        s.delete()
    with pytest.raises(BorradoNoPermitido):
        s.equipo.delete()


def test_consulta_no_puede_registrar(cliente_de, consulta, crear_equipo):
    e = crear_equipo()
    assert cliente_de(consulta).get(f"{reverse('servicios:crear')}?equipo={e.pk}").status_code == 403


def test_lista_exporta(cliente_de, consulta, crear_equipo, calibrar):
    calibrar(crear_equipo(), date(2026, 3, 9))
    c = cliente_de(consulta)
    r = c.get(reverse("servicios:lista"), {"formato": "csv"})
    texto = r.content.decode("utf-8-sig")
    assert r["Content-Type"].startswith("text/csv") and "EQ-0001" in texto and "Conforme" in texto
    assert c.get(reverse("servicios:lista"), {"formato": "xlsx"}).content[:2] == b"PK"
