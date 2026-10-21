"""Códigos QR en SVG para las etiquetas de los equipos y los certificados (RF-14)."""
from io import BytesIO

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.core import signing
from django.urls import reverse


def url_absoluta(ruta):
    return settings.URL_SISTEMA.rstrip("/") + ruta


def qr_svg(url):
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=1)
    buf = BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode()
    return svg[svg.find("<svg"):]


# --- Consulta pública al escanear ---------------------------------------------------------------
# El QR lleva el número del registro firmado: quien escanea ve la ficha sin iniciar sesión, pero nadie
# puede recorrer los demás equipos cambiando el número en la dirección. La firma usa QR_CLAVE, aparte
# de SECRET_KEY, para que las etiquetas ya pegadas sigan funcionando si se cambia la clave de sesiones.

def _firmador(tipo):
    return signing.Signer(key=settings.QR_CLAVE, salt=f"calibralab.qr.{tipo}")


def firmar(tipo, pk):
    return _firmador(tipo).sign(str(pk))


def leer(tipo, token):
    """El pk del registro, o None si el código no es válido."""
    try:
        return int(_firmador(tipo).unsign(token))
    except (signing.BadSignature, ValueError):
        return None


def url_publica_equipo(equipo):
    return url_absoluta(reverse("core:qr_equipo", args=[firmar("equipo", equipo.pk)]))


def url_publica_certificado(servicio):
    return url_absoluta(reverse("core:qr_certificado", args=[firmar("certificado", servicio.pk)]))
