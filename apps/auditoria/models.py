from django.conf import settings
from django.db import models


class Accion(models.TextChoices):
    ALTA = "alta", "Alta"
    MODIFICACION = "modificacion", "Modificación"
    CAMBIO_ESTADO = "cambio_estado", "Cambio de estado"
    INGRESO = "ingreso", "Ingreso al sistema"
    SALIDA = "salida", "Salida del sistema"
    INGRESO_FALLIDO = "ingreso_fallido", "Intento de ingreso fallido"


class RegistroInalterableError(Exception):
    """El registro de cambios no se modifica ni se borra (RNF-12)."""


class RegistroCambio(models.Model):
    """
    Una fila por cada alta, campo modificado, cambio de estado o ingreso (RF-39).

    Solo admite inserciones: el modelo rechaza actualizar o borrar, y un trigger de
    PostgreSQL lo impide también desde fuera de Django (RNF-12).
    """

    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    # Copia del nombre: el registro se lee igual aunque el usuario cambie de nombre.
    usuario_nombre = models.CharField(max_length=150, blank=True)
    accion = models.CharField(max_length=20, choices=Accion.choices, db_index=True)
    modelo = models.CharField("tipo de dato", max_length=100, blank=True, db_index=True)
    objeto_id = models.CharField(max_length=64, blank=True, db_index=True)
    objeto = models.CharField("registro afectado", max_length=255, blank=True)
    # Código del equipo afectado, para filtrar por equipo (RF-40). Lo completan los módulos B en adelante.
    equipo = models.CharField(max_length=64, blank=True, db_index=True)
    campo = models.CharField(max_length=100, blank=True)
    valor_anterior = models.TextField(blank=True)
    valor_nuevo = models.TextField(blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "registro de cambio"
        verbose_name_plural = "registro de cambios"
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.fecha:%Y-%m-%d %H:%M} · {self.usuario_nombre or 'sistema'} · {self.get_accion_display()}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RegistroInalterableError("El registro de cambios no se puede modificar.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RegistroInalterableError("El registro de cambios no se puede borrar.")
