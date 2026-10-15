from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Accion
from .registro import MODELOS_AUDITADOS, escribir, registrar_guardado, valores


@receiver(pre_save)
def capturar_valores_anteriores(sender, instance, raw=False, **kwargs):
    regla = MODELOS_AUDITADOS.get(sender)
    if regla is None or raw:
        return
    anterior = sender._default_manager.filter(pk=instance.pk).first() if instance.pk else None
    instance._auditoria_anteriores = valores(anterior, regla) if anterior else None


@receiver(post_save)
def registrar_cambios(sender, instance, created, raw=False, **kwargs):
    regla = MODELOS_AUDITADOS.get(sender)
    if regla is None or raw:
        return
    if created:
        registrar_guardado(instance, None, regla)
    elif getattr(instance, "_auditoria_anteriores", None) is not None:
        registrar_guardado(instance, instance._auditoria_anteriores, regla)


@receiver(user_logged_in)
def registrar_ingreso(sender, request, user, **kwargs):
    escribir(Accion.INGRESO, usuario=user, objeto=user.username)


@receiver(user_logged_out)
def registrar_salida(sender, request, user, **kwargs):
    if user is not None:
        escribir(Accion.SALIDA, usuario=user, objeto=user.username)


@receiver(user_login_failed)
def registrar_ingreso_fallido(sender, credentials, request=None, **kwargs):
    escribir(Accion.INGRESO_FALLIDO, objeto=str(credentials.get("username", ""))[:255])
