from django.conf import settings
from django.db import models


class TipoAviso(models.TextChoices):
    POR_VENCER = "por_vencer", "Por vencer"
    VENCIDO = "vencido", "Vencido"


class ResultadoEnvio(models.TextChoices):
    ENVIADO = "enviado", "Enviado"
    ERROR = "error", "Error"


class Aviso(models.Model):
    """
    RF-28: correo enviado al responsable de un equipo. La «próxima fecha considerada» ata
    el aviso a una calibración: al registrar la nueva, la fecha cambia y el aviso se cierra solo.
    Es un registro de envíos: no se modifica ni se borra.
    """

    equipo = models.ForeignKey("equipos.Equipo", on_delete=models.PROTECT, related_name="avisos")
    tipo = models.CharField("tipo de aviso", max_length=12, choices=TipoAviso.choices)
    proxima_fecha = models.DateField("próxima fecha considerada", null=True, blank=True)
    destinatario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="avisos")
    correo = models.EmailField("correo")
    enviado_en = models.DateTimeField("fecha y hora de envío", auto_now_add=True)
    resultado = models.CharField("resultado del envío", max_length=10, choices=ResultadoEnvio.choices)
    detalle = models.CharField("detalle del error", max_length=250, blank=True)

    class Meta:
        verbose_name = "aviso por correo"
        verbose_name_plural = "avisos por correo"
        ordering = ["-enviado_en", "-id"]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.equipo.codigo} · {self.enviado_en:%Y-%m-%d %H:%M}"
