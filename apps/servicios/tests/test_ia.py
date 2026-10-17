"""Lectura de certificados con IA. El servicio de IA se simula: las pruebas no salen a internet."""
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.servicios import ia
from apps.servicios.models import LecturaIA

LEIDO = {
    "tipo": "calibracion", "fecha": "2026-03-09", "numero_certificado": "CC-2026-0187",
    "proveedor": "Laboratorio Proveedor Y S.A.", "lugar": "En sitio", "temperatura_ambiente": "20,5",
    "humedad_relativa": "48", "procedimiento": "PC-M-01", "realizado_por": "J. Pérez", "autorizado_por": "",
    "trazabilidad": "INTN",
    "puntos": [
        {"valor_referencia": "100", "valor_leido": "100.2", "error_informado": "0.2", "incertidumbre": "0.05"},
        {"valor_referencia": "500.0", "valor_leido": "", "error_informado": "-0.3", "incertidumbre": ""},
        {"valor_referencia": "2000", "valor_leido": "2000.1", "error_informado": "", "incertidumbre": ""},
    ],
    "patrones": [{"identificacion": "MP-01", "descripcion": "Juego de masas F1", "certificado": "C-123",
                  "proxima_calibracion": "2027-01"}],
    "notas": "La hoja 2 está borrosa.",
}


def respuesta(datos=LEIDO, stop="end_turn"):
    return SimpleNamespace(
        stop_reason=stop, model="claude-opus-5-5",
        content=[SimpleNamespace(type="text", text=json.dumps(datos))],
        usage=SimpleNamespace(input_tokens=6000, output_tokens=900, cache_creation_input_tokens=0,
                              cache_read_input_tokens=0, iterations=None),
    )


@pytest.fixture
def con_ia(settings, monkeypatch):
    settings.IA_CLAVE = "clave-de-prueba"
    settings.IA_MODELO = "claude-opus-5-5"
    llamadas = []

    def falso(datos, extension, equipo, puntos):
        llamadas.append(extension)
        return respuesta()

    monkeypatch.setattr(ia, "_preguntar", falso)
    return llamadas


def pdf(hojas=1):
    cuerpo = b"%PDF-1.4 " + b"<< /Type /Pages >> " + b"<< /Type /Page >> " * hojas
    return SimpleUploadedFile("cert.pdf", cuerpo, content_type="application/pdf")


def leer(cliente, equipo, archivo):
    return cliente.post(f"{reverse('servicios:leer_certificado')}?equipo={equipo.pk}", {"certificado": archivo})


def test_completa_el_formulario_y_registra_el_costo(cliente_de, tecnico, crear_equipo, catalogo, con_ia):
    catalogo["proveedor"].nombre = "Proveedor Y"
    catalogo["proveedor"].save()
    e = crear_equipo()
    r = leer(cliente_de(tecnico), e, pdf())
    assert r.status_code == 200
    d = r.json()
    assert d["campos"]["numero_certificado"] == "CC-2026-0187"
    assert d["campos"]["fecha"] == "2026-03-09" and d["campos"]["temperatura_ambiente"] == "20.5"
    assert d["campos"]["proveedor"] == str(catalogo["proveedor"].pk)
    # Cada punto va a su fila de la ficha; con valor leído no se manda también el error
    assert d["puntos"][0] == {"fila": 0, "valor_referencia": "100", "valor_leido": "100.2", "incertidumbre": "0.05"}
    assert d["puntos"][1] == {"fila": 1, "valor_referencia": "500", "error_informado": "-0.3"}
    assert any("2000" in a for a in d["avisos"])  # el punto que no está en la ficha no se carga
    assert any("borrosa" in a for a in d["avisos"])
    assert d["patrones"][0]["identificacion"] == "MP-01"
    lectura = LecturaIA.objects.get()
    assert lectura.exito and lectura.tokens_entrada == 6000 and lectura.tokens_salida == 900
    assert lectura.costo_usd == Decimal("0.0420")  # 6000 × 4 + 900 × 20 dólares por millón
    assert d["costo_usd"] == "0.0420"


def test_rechaza_mas_de_tres_hojas_sin_gastar(cliente_de, tecnico, crear_equipo, con_ia):
    r = leer(cliente_de(tecnico), crear_equipo(), pdf(hojas=4))
    assert r.status_code == 400 and "4 hojas" in r.json()["error"]
    assert con_ia == [] and not LecturaIA.objects.exists()


def test_sin_clave_no_aparece_ni_responde(cliente_de, tecnico, crear_equipo, settings):
    settings.IA_CLAVE = ""
    e = crear_equipo()
    c = cliente_de(tecnico)
    assert "Leer el certificado con IA" not in c.get(f"{reverse('servicios:crear')}?equipo={e.pk}").content.decode()
    r = leer(c, e, pdf())
    assert r.status_code == 400 and "ANTHROPIC_API_KEY" in r.json()["error"]


def test_con_clave_aparece_el_boton(cliente_de, tecnico, crear_equipo, con_ia):
    html = cliente_de(tecnico).get(f"{reverse('servicios:crear')}?equipo={crear_equipo().pk}").content.decode()
    assert "Leer el certificado con IA" in html


def test_respuesta_rechazada_queda_registrada(cliente_de, tecnico, crear_equipo, con_ia, monkeypatch):
    monkeypatch.setattr(ia, "_preguntar", lambda *a: respuesta(stop="refusal"))
    r = leer(cliente_de(tecnico), crear_equipo(), pdf())
    assert r.status_code == 400
    lectura = LecturaIA.objects.get()
    assert not lectura.exito and "refusal" in lectura.mensaje


def test_formato_no_admitido(cliente_de, tecnico, crear_equipo, con_ia):
    archivo = SimpleUploadedFile("cert.docx", b"x")
    r = leer(cliente_de(tecnico), crear_equipo(), archivo)
    assert r.status_code == 400 and "PDF" in r.json()["error"]


def test_consulta_no_puede_leer(cliente_de, consulta, crear_equipo, con_ia):
    assert leer(cliente_de(consulta), crear_equipo(), pdf()).status_code == 403


def test_registro_de_lecturas_solo_administrador(cliente_de, admin, tecnico, crear_equipo, con_ia):
    leer(cliente_de(tecnico), crear_equipo(), pdf())
    assert cliente_de(tecnico).get(reverse("servicios:lecturas_ia")).status_code == 403
    html = cliente_de(admin).get(reverse("servicios:lecturas_ia")).content.decode()
    assert "cert.pdf" in html and "0,0420" in html


def test_costo_suma_cada_intento(settings):
    """Si el modelo pedido declina y responde otro, se cobran los dos intentos."""
    u = SimpleNamespace(input_tokens=1000, output_tokens=0, model="claude-opus-5-5")
    v = SimpleNamespace(input_tokens=1000, output_tokens=1000, model="claude-opus-5")
    r = SimpleNamespace(usage=SimpleNamespace(iterations=[u, v]))
    entrada, salida, costo = ia._costo(r, "claude-opus-5-5")
    assert (entrada, salida) == (2000, 1000)
    assert costo == Decimal("0.0340")  # 0.004 + 0.005 + 0.025
