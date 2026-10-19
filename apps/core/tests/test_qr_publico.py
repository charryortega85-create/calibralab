"""Consulta pública al escanear un QR: se ven los datos sin iniciar sesión, solo del registro escaneado."""
import io
from datetime import date

from django.urls import reverse

from apps.core.qr import firmar, url_publica_certificado, url_publica_equipo

def jpg():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (600, 800), "white").save(buf, "JPEG")
    return buf.getvalue()


def pdf_de(hojas):
    """Un PDF real de varias hojas, hecho con Pillow."""
    from PIL import Image

    buf = io.BytesIO()
    paginas = [Image.new("RGB", (595, 842), "white") for _ in range(hojas)]
    paginas[0].save(buf, "PDF", save_all=True, append_images=paginas[1:])
    return buf.getvalue()


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
    assert "Historial del equipo" in html and "Datos del equipo" not in html
    assert 'name="robots" content="noindex' in html
    assert "Cerrar sesión" not in html  # no muestra el menú interno


def test_certificado_se_ve_hoja_por_hoja_sin_el_archivo_original(client, crear_equipo, calibrar):
    s = calibrar(crear_equipo(), date(2026, 3, 9), numero="CC-2026-7")
    original = pdf_de(2)
    s.certificado.save("cert.pdf", io.BytesIO(original), save=True)
    s.anexos.create(titulo="Foto", archivo=__import__("django.core.files.base", fromlist=["ContentFile"])
                    .ContentFile(jpg(), "hoja3.jpg"), subido_por=s.registrado_por)
    token = firmar("certificado", s.pk)
    r = client.get(reverse("core:qr_certificado", args=[token]))
    html = r.content.decode()
    assert "CC-2026-7" in html and "Es el último del equipo" in html and "no se puede descargar" in html
    assert html.count('class="visor-hoja"') == 3 and "Abrir" not in html and ".pdf" not in html
    assert r["Cache-Control"] == "no-store, private"
    for n, p in [(0, 0), (0, 1), (1, 0)]:
        h = client.get(reverse("core:qr_hoja", args=[token, n, p]), HTTP_SEC_FETCH_DEST="empty")
        assert h.status_code == 200 and h["Content-Type"] == "image/jpeg" and h.content != original
        assert h["Content-Disposition"] == "inline"
    assert client.get(reverse("core:qr_hoja", args=[token, 0, 2])).status_code == 404
    assert client.get(reverse("core:qr_hoja", args=[token, 2, 0])).status_code == 404
    # Abrir la imagen sola en una pestaña (para guardarla) no funciona
    assert client.get(reverse("core:qr_hoja", args=[token, 0, 0]), HTTP_SEC_FETCH_DEST="document").status_code == 404


def test_la_hoja_lleva_marca_de_agua(tmp_path):
    from PIL import Image

    from apps.core import visor

    ruta = tmp_path / "c.jpg"
    ruta.write_bytes(jpg())
    img = Image.open(io.BytesIO(visor.pagina_jpg(ruta, 0))).convert("RGB")
    colores = {img.getpixel((x, y)) for x in range(0, img.width, 7) for y in range(0, img.height, 7)}
    assert len(colores) > 5  # ya no es una hoja en blanco: tiene la marca y el pie


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
