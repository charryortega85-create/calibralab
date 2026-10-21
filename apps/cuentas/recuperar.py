"""
RF-04: recuperar la contraseña con un enlace enviado por correo.

El enlace lleva un código que Django firma con la contraseña actual: sirve una sola vez (al
cambiarla deja de valer) y vence a las PASSWORD_RESET_TIMEOUT. Lo puede pedir la persona desde
la pantalla de ingreso o enviárselo el administrador.
"""
from django.conf import settings
from django.contrib.auth.password_validation import password_validators_help_texts
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.mail import send_mail
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import Usuario

ESPERA = 120  # segundos entre dos pedidos para el mismo usuario, para no llenarle el correo


def horas():
    return settings.PASSWORD_RESET_TIMEOUT // 3600


def enlace(usuario):
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    return settings.URL_SISTEMA.rstrip("/") + reverse("cuentas:nueva_contrasena", args=[uid, token])


def enviar_enlace(usuario, por_admin=False):
    """Envía el correo. Devuelve el error como texto, o None si salió bien."""
    # Las reglas salen de los validadores de settings: si cambian, el correo cambia solo.
    contexto = {"usuario": usuario, "url": enlace(usuario), "horas": horas(), "por_admin": por_admin,
                "reglas": password_validators_help_texts()}
    try:
        send_mail("[CalibraLab] Crea tu contraseña nueva", render_to_string("registration/correo_recuperar.txt", contexto),
                  None, [usuario.email])
    except Exception as exc:
        return str(exc)[:250]
    return None


def pedir(dato):
    """La persona escribió su usuario o su correo. No se le dice si existe, para no revelar usuarios."""
    dato = (dato or "").strip()
    if not dato:
        return
    usuario = Usuario.objects.filter(Q(username__iexact=dato) | Q(email__iexact=dato), is_active=True).first()
    if usuario and usuario.email and cache.add(f"recuperar:{usuario.pk}", 1, ESPERA):
        enviar_enlace(usuario)
