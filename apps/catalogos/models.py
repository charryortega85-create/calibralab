from django.db import models

from apps.core.modelos import Catalogo


class Marca(Catalogo):
    class Meta(Catalogo.Meta):
        verbose_name = "marca"
        verbose_name_plural = "marcas"


class Laboratorio(Catalogo):
    class Meta(Catalogo.Meta):
        verbose_name = "laboratorio"
        verbose_name_plural = "laboratorios"

    @property
    def filtro(self):
        """Valor del filtro de la lista de equipos que trae todas sus áreas."""
        return f"lab-{self.pk}"


class Area(Catalogo):
    """Área de un laboratorio. Cada equipo pertenece a un área y cada usuario trabaja en una o varias."""

    laboratorio = models.ForeignKey(Laboratorio, on_delete=models.PROTECT, related_name="areas",
                                    verbose_name="laboratorio")
    nombre = models.CharField("nombre", max_length=120)

    class Meta(Catalogo.Meta):
        verbose_name = "área"
        verbose_name_plural = "áreas"
        ordering = ["laboratorio__nombre", "nombre"]
        constraints = [models.UniqueConstraint(fields=["laboratorio", "nombre"], name="area_unica_por_laboratorio",
                                               violation_error_message="Ese laboratorio ya tiene un área con ese nombre.")]

    def __str__(self):
        return f"{self.laboratorio} · {self.nombre}"


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
