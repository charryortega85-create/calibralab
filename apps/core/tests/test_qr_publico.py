"""Consulta pública al escanear un QR: se ven los datos sin iniciar sesión, solo del registro escaneado."""
import io
from datetime import date

from django.urls import reverse

from apps.core.qr import firmar, url_publica_certificado, url_publica_equipo

JPG = b"\xff\xd8\xff\xe0 foto de prueba"


def test_el_qr_de_la_etiqueta_abre_la_consulta_publica(cliente_de, consulta, crear_equipo, client):
    e = crear_equipo()
    html = cliente_de(consulta).get(reverse("equipos:etiqueta", args=[e.pk])).content.decode()
    assert url_publica_equipo(e) in html


def test_equipo_se_ve_sin_iniciar_sesion(client, crear_equipo, calibrar):
    e = crear_equipo()
    calibrar(e, date(2026, 3, 9), numero="CC-2026-7")
    r = client.get(reverse("core:qr_equipo", args=[firmar("equipo", e.pk)]))
    html = r.content.decode()
    assert r.status_code == 200
    assert "EQ-0001" in html and "SN-EQ-0001" in html and "CC-2026-7" in html and "Próxima calibración" in html
    assert 'name="robots" content="noindex' in html
    assert "Cerrar sesión" not in html  # no muestra el menú interno


def test_certificado_se_ve_sin_iniciar_sesion_con_su_archivo(client, crear_equipo, calibrar):
    s = calibrar(crear_equipo(), date(2026, 3, 9), numero="CC-2026-7")
    s.certificado.save("cert.jpg", io.BytesIO(JPG), save=True)
    token = firmar("certificado", s.pk)
    html = client.get(reverse("core:qr_certificado", args=[token])).content.decode()
    assert "CC-2026-7" in html and "Resultados por punto" in html and "Es el último del equipo" in html
    r = client.get(reverse("core:qr_archivo", args=[token, 0]))
    assert r.status_code == 200 and b"".join(r.streaming_content) == JPG
    assert client.get(reverse("core:qr_archivo", args=[token, 1])).status_code == 404


def test_no_se_puede_adivinar_otro_registro(client, crear_equipo, calibrar):
    e1, e2 = crear_equipo("EQ-0001"), crear_equipo("EQ-0002")
    token = firmar("equipo", e1.pk)
    falso = token.replace(f"{e1.pk}:", f"{e2.pk}:", 1)
    assert client.get(reverse("core:qr_equipo", args=[falso])).status_code == 404
    assert client.get(reverse("core:qr_equipo", args=[str(e2.pk)])).status_code == 404
    # Un código de equipo no sirve para abrir un certificado con el mismo número.
    s = calibrar(e1, date(2026, 3, 9))
    assert client.get(reverse("core:qr_certificado", args=[firmar("equipo", s.pk)])).status_code == 404


def test_la_pagina_interna_y_los_demas_archivos_siguen_pidiendo_sesion(client, crear_equipo, calibrar):
    s = calibrar(crear_equipo(), date(2026, 3, 9))
    s.certificado.save("cert.pdf", io.BytesIO(b"%PDF-1.4"), save=True)
    assert client.get(reverse("servicios:certificado", args=[s.pk])).status_code == 302
    assert client.get(reverse("core:archivo", args=[s.certificado.name])).status_code == 302


def test_el_qr_del_certificado_apunta_a_la_consulta_publica(cliente_de, consulta, crear_equipo, calibrar, settings):
    settings.URL_SISTEMA = "http://192.168.1.50:8000"
    s = calibrar(crear_equipo(), date(2026, 3, 9))
    url = url_publica_certificado(s)
    assert url.startswith("http://192.168.1.50:8000/qr/certificado/")
    assert url in cliente_de(consulta).get(reverse("servicios:certificado", args=[s.pk])).content.decode()
