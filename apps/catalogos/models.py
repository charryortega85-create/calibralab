from django.db import models

from apps.core.modelos import Catalogo


class Marca(Catalogo):
    class Meta(Catalogo.Meta):
        verbose_name = "marca"
        verbose_name_plural = "marcas"


class Ubicacion(Catalogo):
    class Meta(Catalogo.Meta):
        verbose_name = "ubicación"
        verbose_name_plural = "ubicaciones"


class Unidad(Catalogo):
    simbolo = models.CharField("símbolo", max_length=20, unique=True)
    magnitud = models.CharField("magnitud", max_length=60, blank=True, help_text="Por ejemplo: masa, temperatura, volumen.")

    class Meta(Catalogo.Meta):
        verbose_name = "unidad de medida"
        verbose_name_plural = "unidades de medida"

    def __str__(self):
        return self.simbolo


class Proveedor(Catalogo):
    ruc = models.CharField("RUC", max_length=30, blank=True)
    contacto = models.CharField("persona de contacto", max_length=120, blank=True)
    correo = models.EmailField("correo", blank=True)
    telefono = models.CharField("teléfono", max_length=40, blank=True)
    acreditacion = models.CharField(
        "acreditación", max_length=120, blank=True, help_text="Organismo y n.º de acreditación, si tiene (sostiene la trazabilidad)."
    )

    class Meta(Catalogo.Meta):
        verbose_name = "proveedor"
        verbose_name_plural = "proveedores"
