"""
Visor de certificados de la consulta por QR: cada hoja se envía como imagen con una marca de
agua, nunca el archivo original. Así el certificado se puede leer en el teléfono pero no
descargar, y una captura de pantalla queda marcada como «solo consulta» con la fecha y hora.
"""
import io
from pathlib import Path

from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

IMAGENES = ("jpg", "jpeg", "png", "webp")
ESCALA_PDF = 1.6          # unos 115 ppp: se lee bien en pantalla y no sirve para reimprimir
ANCHO_MAXIMO = 1400


def _extension(ruta):
    return Path(ruta).suffix.lower().lstrip(".")


def visible(ruta):
    return _extension(ruta) in IMAGENES + ("pdf",)


def contar_paginas(ruta):
    ext = _extension(ruta)
    if ext in IMAGENES:
        return 1
    if ext != "pdf":
        return 0
    try:
        import pypdfium2 as pdfium

        with open(ruta, "rb") as f:
            return len(pdfium.PdfDocument(f.read()))
    except Exception:  # PDF dañado o biblioteca ausente: no se muestra
        return 0


def _hoja(ruta, n):
    if _extension(ruta) in IMAGENES:
        return Image.open(ruta).convert("RGB")
    import pypdfium2 as pdfium

    with open(ruta, "rb") as f:
        pdf = pdfium.PdfDocument(f.read())
    return pdf[n].render(scale=ESCALA_PDF).to_pil().convert("RGB")


def _marca_de_agua(img):
    w, h = img.size
    texto = f"SOLO CONSULTA · CalibraLab · {timezone.localtime():%Y-%m-%d %H:%M}"
    tam = max(18, w // 34)
    fuente = ImageFont.load_default(size=tam)
    capa = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    paso_x = int(d.textlength(texto, font=fuente)) + tam * 3
    for fila, y in enumerate(range(0, h * 2, tam * 6)):
        for x in range(-paso_x + (fila % 2) * paso_x // 2, w * 2, paso_x):
            d.text((x, y), texto, font=fuente, fill=(200, 30, 30, 60))
    capa = capa.rotate(30, resample=Image.BICUBIC).crop((w // 2, h // 2, w // 2 + w, h // 2 + h))
    salida = Image.alpha_composite(img.convert("RGBA"), capa)
    pie = ImageDraw.Draw(salida)
    pie.rectangle((0, h - tam * 2, w, h), fill=(255, 255, 255, 230))
    pie.text((tam, h - tam * 1.6), "Copia no controlada · solo para consulta en pantalla", font=fuente,
             fill=(120, 20, 20, 255))
    return salida.convert("RGB")


def pagina_jpg(ruta, n):
    img = _hoja(ruta, n)
    if img.width > ANCHO_MAXIMO:
        img = img.resize((ANCHO_MAXIMO, round(img.height * ANCHO_MAXIMO / img.width)), Image.LANCZOS)
    buf = io.BytesIO()
    _marca_de_agua(img).save(buf, "JPEG", quality=80, optimize=True)
    return buf.getvalue()
