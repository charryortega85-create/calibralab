"""
Piezas comunes de los modelos.

RN-07 y RNF-09: nada se borra ni se sobrescribe. Cada modelo de datos hereda de
`ModeloVersionado`: guarda cada versión con fecha, usuario y motivo
(django-simple-history) y rechaza el borrado.
"""
from django.db import models
from simple_history.models import HistoricalRecords


class BorradoNoPermitido(Exception):
    pass


class ModeloVersionado(models.Model):
    creado = models.DateTimeField("creado", auto_now_add=True)
    modificado = models.DateTimeField("modificado", auto_now=True)
    history = HistoricalRecords(inherit=True)

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        raise BorradoNoPermitido(
            f"{self._meta.verbose_name} no se puede borrar: se conserva con todo su historial (RN-07)."
        )

    def versiones(self):
        return self.history.select_related("history_user").order_by("-history_date", "-history_id")


class Catalogo(ModeloVersionado):
    """Lista controlada (RF-08): se desactiva en lugar de borrarse."""

    nombre = models.CharField("nombre", max_length=120, unique=True)
    activo = models.BooleanField("activo", default=True)

    class Meta:
        abstract = True
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
