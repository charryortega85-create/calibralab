"""Códigos QR en SVG para las etiquetas de los equipos y los certificados (RF-14)."""
from io import BytesIO

import qrcode
import qrcode.image.svg
from django.conf import settings


def url_absoluta(ruta):
    return settings.URL_SISTEMA.rstrip("/") + ruta


def qr_svg(url):
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=1)
    buf = BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode()
    return svg[svg.find("<svg"):]
