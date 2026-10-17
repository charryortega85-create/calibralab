from django import forms
from django.conf import settings


def validar_adjunto(archivo, obligatorio=False):
    """Revisa la extensión y el tamaño de un archivo adjunto (RNF-08)."""
    if not archivo:
        if obligatorio:
            raise forms.ValidationError("Adjunta el archivo.")
        return archivo
    ext = archivo.name.rsplit(".", 1)[-1].lower() if "." in archivo.name else ""
    if ext not in settings.EXTENSIONES_PERMITIDAS:
        raise forms.ValidationError(
            f"Formato no admitido. Usa uno de estos: {', '.join(settings.EXTENSIONES_PERMITIDAS)}."
        )
    limite = settings.TAMANO_MAXIMO_ADJUNTO_MB
    if archivo.size > limite * 1024 * 1024:
        raise forms.ValidationError(f"El archivo pesa más de {limite} MB.")
    return archivo
