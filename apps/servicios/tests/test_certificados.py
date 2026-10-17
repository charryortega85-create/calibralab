"""Archivo de certificados y consulta por QR."""
import io
import zipfile
from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.servicios.models import AnexoServicio, PatronUtilizado, Servicio
from apps.servicios.tests.test_servicios import datos_calibracion

JPG = b"\xff\xd8\xff\xe0 foto de prueba"


def test_registrar_datos_del_certificado_y_patrones(cliente_de, tecnico, crear_equipo, catalogo):
    e = crear_equipo()
    datos = datos_calibracion(catalogo["proveedor"], [("100", "100.1")], **{
        "lugar": "Laboratorio del proveedor", "temperatura_ambiente": "20.4", "humedad_relativa": "62",
        "procedimiento": "PRO-C02 Rev.04", "realizado_por": "Técnico del proveedor", "autorizado_por": "Jefa técnica",
        "patrones-TOTAL_FORMS": 3, "patrones-INITIAL_FORMS": 0,
        "patrones-0-identificacion": "PCT-15", "patrones-0-descripcion": "Termohigrómetro",
        "patrones-0-certificado": "CP-2026-1", "patrones-0-proxima_calibracion": "2027-04"})
    r = cliente_de(tecnico).post(f"{reverse('servicios:crear')}?equipo={e.pk}", datos)
    assert r.status_code == 302
    s = Servicio.objects.get()
    assert s.lugar == "Laboratorio del proveedor" and s.humedad_relativa == 62 and s.autorizado_por == "Jefa técnica"
    assert list(s.patrones.values_list("identificacion", "proxima_calibracion")) == [("PCT-15", "2027-04")]


def test_proxima_del_patron_con_formato_aaaa_mm(cliente_de, tecnico, crear_equipo, catalogo):
    e = crear_equipo()
    datos = datos_calibracion(catalogo["proveedor"], [("100", "100.1")], **{
        "patrones-TOTAL_FORMS": 1, "patrones-INITIAL_FORMS": 0,
        "patrones-0-identificacion": "PCT-15", "patrones-0-proxima_calibracion": "04/2027"})
    r = cliente_de(tecnico).post(f"{reverse('servicios:crear')}?equipo={e.pk}", datos)
    assert r.status_code == 200 and "AAAA-MM" in r.content.decode() and not Servicio.objects.exists()


def test_pagina_del_certificado_con_qr_y_archivo(cliente_de, consulta, crear_equipo, calibrar):
    s = calibrar(crear_equipo(), date(2026, 3, 9))
    s.certificado.save("cert.jpg", io.BytesIO(JPG), save=True)
    PatronUtilizado.objects.create(servicio=s, identificacion="PCT-79-2", descripcion="Termómetro digital")
    html = cliente_de(consulta).get(reverse("servicios:certificado", args=[s.pk])).content.decode()
    assert "<svg" in html and "PCT-79-2" in html and "<img" in html and "Es el último del equipo" in html
    assert "Agregar página" not in html  # Consulta solo mira


def test_sin_sesion_la_pagina_interna_pide_ingresar(client, crear_equipo, calibrar):
    s = calibrar(crear_equipo(), date(2026, 3, 9))
    url = reverse("servicios:certificado", args=[s.pk])
    r = client.get(url)
    assert r.status_code == 302 and "next=" in r.url


def test_archivo_se_puede_mostrar_dentro_de_la_pagina(cliente_de, consulta, crear_equipo, calibrar):
    s = calibrar(crear_equipo(), date(2026, 3, 9))
    s.certificado.save("cert.pdf", io.BytesIO(b"%PDF-1.4"), save=True)
    r = cliente_de(consulta).get(reverse("core:archivo", args=[s.certificado.name]))
    assert r.status_code == 200 and r["X-Frame-Options"] == "SAMEORIGIN"


def test_agregar_pagina_al_certificado(cliente_de, tecnico, consulta, crear_equipo, calibrar):
    s = calibrar(crear_equipo(), date(2026, 3, 9))
    url = reverse("servicios:anexo", args=[s.pk])
    assert cliente_de(consulta).get(url).status_code == 403
    c = cliente_de(tecnico)
    r = c.post(url, {"titulo": "Página 2 de 2", "archivo": SimpleUploadedFile("p2.exe", b"x")})
    assert r.status_code == 200 and not AnexoServicio.objects.exists()
    c.post(url, {"titulo": "Página 2 de 2", "archivo": SimpleUploadedFile("p2.jpg", JPG)})
    a = AnexoServicio.objects.get()
    assert a.subido_por == tecnico and "Página 2 de 2" in c.get(reverse("servicios:certificado", args=[s.pk])).content.decode()


def test_archivo_busca_filtra_y_descarga_zip(cliente_de, consulta, crear_equipo, calibrar):
    e = crear_equipo()
    viejo = calibrar(e, date(2025, 3, 9), numero="CC-2025-1")
    nuevo = calibrar(e, date(2026, 3, 9), numero="CC-2026-1")
    nuevo.certificado.save("cert.pdf", io.BytesIO(b"%PDF-1.4 nuevo"), save=True)
    AnexoServicio.objects.create(servicio=nuevo, titulo="Página 2", archivo=SimpleUploadedFile("p2.jpg", JPG),
                                 subido_por=e.responsable)
    PatronUtilizado.objects.create(servicio=viejo, identificacion="PCT-12")
    c = cliente_de(consulta)
    url = reverse("servicios:certificados")
    html = c.get(url).content.decode()
    assert "CC-2025-1" in html and "CC-2026-1" in html and "Sin archivo" in html
    html = c.get(url, {"q": "PCT-12"}).content.decode()
    assert "CC-2025-1" in html and "CC-2026-1" not in html
    html = c.get(url, {"vigentes": "1"}).content.decode()
    assert "CC-2026-1" in html and "CC-2025-1" not in html
    r = c.get(url, {"formato": "zip"})
    nombres = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert nombres == ["EQ-0001/2026-03-09_CC-2026-1.pdf", "EQ-0001/2026-03-09_CC-2026-1_1.jpg"]


def test_menu_marca_solo_certificados(cliente_de, consulta):
    html = cliente_de(consulta).get(reverse("servicios:certificados")).content.decode()
    assert html.count('aria-current="page"') == 1
