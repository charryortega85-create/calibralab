from datetime import date, timedelta
from decimal import Decimal as D

import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.core.modelos import BorradoNoPermitido
from apps.equipos.models import EstadoEquipo
from apps.servicios.models import DecisionNoApto, Resultado, Servicio


def pdf():
    return SimpleUploadedFile("cert.pdf", b"%PDF-1.4 prueba", content_type="application/pdf")


def datos_calibracion(proveedor, lecturas, **extra):
    datos = {"tipo": "calibracion", "fecha": (timezone.localdate() - timedelta(days=1)).isoformat(),
             "proveedor": proveedor.pk, "numero_certificado": "CC-2026-0001", "regla": "simple",
             "certificado": pdf(), "puntos-TOTAL_FORMS": len(lecturas), "puntos-INITIAL_FORMS": 0,
             "patrones-TOTAL_FORMS": 0, "patrones-INITIAL_FORMS": 0}
    for i, (ref, leido) in enumerate(lecturas):
        datos[f"puntos-{i}-valor_referencia"] = ref
        datos[f"puntos-{i}-valor_leido"] = leido
    datos.update(extra)
    return datos


def test_calibracion_apta_calcula_proxima_fecha(cliente_de, tecnico, crear_equipo, catalogo):
    e = crear_equipo()
    r = cliente_de(tecnico).post(f"{reverse('servicios:crear')}?equipo={e.pk}", datos_calibracion(
        catalogo["proveedor"], [("100", "100.2"), ("500", "499.7"), ("1000", "1000.4")]))
    s = Servicio.objects.get()
    assert r.status_code == 302 and r.url == s.get_absolute_url()
    assert s.resultado == Resultado.CONFORME and s.dictamen == "Conforme"
    ayer = timezone.localdate() - timedelta(days=1)
    assert s.proxima_fecha == s.proxima_fecha_calculada == ayer.replace(year=ayer.year + 1)
    assert [p.cumple for p in s.puntos.all()] == [True, True, True]
    assert s.puntos.first().emp_aplicado == D("0.5")


def test_no_apto_pide_decision_y_pasa_a_fuera_de_servicio(cliente_de, tecnico, crear_equipo, catalogo, calibrar):
    e = crear_equipo()
    anterior = calibrar(e, date(2025, 9, 10))
    c = cliente_de(tecnico)
    r = c.post(f"{reverse('servicios:crear')}?equipo={e.pk}",
               datos_calibracion(catalogo["proveedor"], [("100", "100.9"), ("500", "500"), ("1000", "1000")]))
    s = Servicio.objects.exclude(pk=anterior.pk).get()
    assert s.resultado == Resultado.NO_CONFORME and s.proxima_fecha is None
    assert r.url == reverse("servicios:decision", args=[s.pk])
    c.post(reverse("servicios:decision", args=[s.pk]), {"decision": "fuera_servicio"})
    d = DecisionNoApto.objects.get()
    e.refresh_from_db()
    assert e.estado == EstadoEquipo.FUERA_DE_SERVICIO
    assert d.fuera_tolerancia_desde == date(2025, 9, 10) and d.decidido_por == tecnico
    assert e.cambios_estado.get().motivo.startswith("Calibración no apta")


def test_mantener_estado_exige_justificacion(cliente_de, tecnico, crear_equipo, calibrar):
    e = crear_equipo()
    s = calibrar(e, date(2026, 9, 1), resultado="no_conforme")
    r = cliente_de(tecnico).post(reverse("servicios:decision", args=[s.pk]), {"decision": "mantener"})
    assert r.status_code == 200 and not DecisionNoApto.objects.exists()


def test_rn08_calibracion_sin_certificado_se_rechaza(cliente_de, tecnico, crear_equipo, catalogo):
    e = crear_equipo()
    datos = datos_calibracion(catalogo["proveedor"], [("100", "100.1")])
    datos.pop("certificado")
    r = cliente_de(tecnico).post(f"{reverse('servicios:crear')}?equipo={e.pk}", datos)
    assert r.status_code == 200 and "obligatorio (RN-08)" in r.content.decode()
    assert not Servicio.objects.exists()


def test_fecha_futura_se_rechaza(cliente_de, tecnico, crear_equipo, catalogo):
    e = crear_equipo()
    datos = datos_calibracion(catalogo["proveedor"], [("100", "100.1")],
                              fecha=(timezone.localdate() + timedelta(days=1)).isoformat())
    r = cliente_de(tecnico).post(f"{reverse('servicios:crear')}?equipo={e.pk}", datos)
    assert "no puede ser futura" in r.content.decode() and not Servicio.objects.exists()


def test_fecha_manual_exige_justificacion(cliente_de, tecnico, crear_equipo, catalogo):
    e = crear_equipo()
    datos = datos_calibracion(catalogo["proveedor"], [("100", "100.1")], proxima_manual="2027-01-01")
    r = cliente_de(tecnico).post(f"{reverse('servicios:crear')}?equipo={e.pk}", datos)
    assert "justificación" in r.content.decode() and not Servicio.objects.exists()
    datos = datos_calibracion(catalogo["proveedor"], [("100", "100.1")], proxima_manual="2027-01-01",
                              justificacion_proxima="Se alinea con el lote de balanzas")
    cliente_de(tecnico).post(f"{reverse('servicios:crear')}?equipo={e.pk}", datos)
    s = Servicio.objects.get()
    assert s.proxima_fecha == date(2027, 1, 1) and s.proxima_fecha != s.proxima_fecha_calculada


def test_calificacion_registra_resultado_y_vigencia(cliente_de, tecnico, crear_equipo, catalogo):
    e = crear_equipo()
    r = cliente_de(tecnico).post(f"{reverse('servicios:crear')}?equipo={e.pk}", {
        "tipo": "calificacion", "fecha": "2026-01-10", "proveedor": catalogo["proveedor"].pk,
        "numero_certificado": "CQ-1", "resultado": "conforme", "vigencia_hasta": "2027-01-10",
        "puntos-TOTAL_FORMS": 0, "puntos-INITIAL_FORMS": 0, "patrones-TOTAL_FORMS": 0, "patrones-INITIAL_FORMS": 0})
    assert r.status_code == 302, re.findall(r'class="(?:err|error)[^"]*"[^>]*>([^<]+)', r.content.decode())
    s = Servicio.objects.get()
    assert r.status_code == 302 and s.dictamen == "Conforme" and s.proxima_fecha is None


def test_rn07_correccion_conserva_version_y_motivo(cliente_de, tecnico, crear_equipo, calibrar_con_puntos, catalogo):
    e = crear_equipo()
    s = calibrar_con_puntos(e, date(2026, 3, 9))
    p = s.puntos.order_by("orden")
    datos = {"fecha": "2026-03-09", "proveedor": catalogo["proveedor"].pk, "numero_certificado": "CC-1-BIS",
             "regla": "simple", "motivo": "Error de transcripción del certificado", "certificado": pdf(),
             "puntos-TOTAL_FORMS": 3, "puntos-INITIAL_FORMS": 3, "patrones-TOTAL_FORMS": 0, "patrones-INITIAL_FORMS": 0}
    for i, punto in enumerate(p):
        datos.update({f"puntos-{i}-id": punto.pk, f"puntos-{i}-valor_referencia": punto.valor_referencia,
                      f"puntos-{i}-valor_leido": punto.valor_leido})
    datos["puntos-2-valor_leido"] = "1000.7"
    r = cliente_de(tecnico).post(reverse("servicios:corregir", args=[s.pk]), datos)
    assert r.status_code == 302, r.content.decode()[:500]
    s.refresh_from_db()
    assert s.numero_certificado == "CC-1-BIS" and s.resultado == Resultado.NO_CONFORME
    versiones = list(s.versiones())
    assert any(v.numero_certificado == "CC-1" for v in versiones)
    assert any(v.history_change_reason == "Error de transcripción del certificado" for v in versiones)


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
