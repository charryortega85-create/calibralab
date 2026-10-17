
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.modelos import ModeloVersionado


class Criticidad(models.TextChoices):
    ALTA = "alta", "Alta"
    MEDIA = "media", "Media"
    BAJA = "baja", "Baja"


ORDEN_CRITICIDAD = {Criticidad.ALTA: 0, Criticidad.MEDIA: 1, Criticidad.BAJA: 2}


class EstadoEquipo(models.TextChoices):
    """Estado actual del equipo (RF-11). No confundir con el estado de calibración (RN-03)."""

    EN_SERVICIO = "en_servicio", "En servicio"
    EN_REPARACION = "en_reparacion", "En reparación"
    FUERA_DE_SERVICIO = "fuera_servicio", "Fuera de servicio"
    BAJA = "baja", "De baja"


class TipoEMP(models.TextChoices):
    """RF-07: tres maneras de definir el error máximo permitido."""

    FIJO = "fijo", "Valor fijo"
    PCT_LECTURA = "pct_lectura", "% de la lectura"
    PCT_ALCANCE = "pct_alcance", "% del alcance"


def ruta_documento(instancia, nombre):
    return f"equipos/{instancia.equipo.codigo}/documentos/{nombre}"


class Equipo(ModeloVersionado):
    # --- Identificación (RF-05) ---
    codigo = models.CharField("código interno", max_length=30, unique=True,
                              help_text="Único en el laboratorio, por ejemplo EQ-0001 (RN-01).")
    patrimonio = models.CharField("n.º de patrimonio", max_length=40, blank=True)
    descripcion = models.CharField("descripción", max_length=200)
    marca = models.ForeignKey("catalogos.Marca", on_delete=models.PROTECT, verbose_name="marca")
    modelo = models.CharField("modelo", max_length=80)
    numero_serie = models.CharField("n.º de serie", max_length=80)
    area = models.ForeignKey("catalogos.Area", on_delete=models.PROTECT, null=True, blank=True, related_name="equipos",
                             verbose_name="laboratorio y área")
    ubicacion = models.ForeignKey("catalogos.Ubicacion", on_delete=models.PROTECT, verbose_name="ubicación")
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="equipos",
                                    verbose_name="responsable")
    asignado_a = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="instrumentos",
                                   verbose_name="asignado al equipo",
                                   help_text="Si es un instrumento de otro equipo, por ejemplo el termómetro de una estufa.")
    # --- Ficha técnica (RF-06) ---
    unidad = models.ForeignKey("catalogos.Unidad", on_delete=models.PROTECT, verbose_name="unidad de medida")
    rango_min = models.DecimalField("rango desde", max_digits=14, decimal_places=6, null=True, blank=True)
    rango_max = models.DecimalField("rango hasta", max_digits=14, decimal_places=6, null=True, blank=True)
    resolucion = models.DecimalField("resolución", max_digits=14, decimal_places=6, null=True, blank=True,
                                     validators=[MinValueValidator(0)])
    capacidad = models.DecimalField("capacidad o alcance", max_digits=14, decimal_places=6, null=True, blank=True,
                                    validators=[MinValueValidator(0)],
                                    help_text="Se usa cuando el EMP es un % del alcance.")
    tolerancia = models.CharField("tolerancia", max_length=120, blank=True)
    criticidad = models.CharField("criticidad", max_length=10, choices=Criticidad.choices, default=Criticidad.MEDIA)
    intervalo_meses = models.PositiveSmallIntegerField("intervalo de calibración (meses)", default=12,
                                                       validators=[MinValueValidator(1)])
    # --- Estado actual (RF-11) ---
    estado = models.CharField("estado actual", max_length=20, choices=EstadoEquipo.choices,
                              default=EstadoEquipo.EN_SERVICIO)
    observaciones = models.TextField("observaciones", blank=True)

    class Meta:
        verbose_name = "equipo"
        verbose_name_plural = "equipos"
        ordering = ["codigo"]
        constraints = [
            # RN-01: no se repite la combinación de marca, modelo y número de serie.
            models.UniqueConstraint(fields=["marca", "modelo", "numero_serie"], name="equipo_marca_modelo_serie_unico",
                                    violation_error_message="Ya existe un equipo con esa marca, modelo y número de serie (RN-01)."),
        ]

    def __str__(self):
        return f"{self.codigo} · {self.descripcion}"

    def get_absolute_url(self):
        return reverse("equipos:ficha", args=[self.pk])

    @property
    def de_baja(self):
        return self.estado == EstadoEquipo.BAJA

    def cambiar_estado(self, nuevo, motivo, usuario, fecha=None):
        """RF-11: deja constancia de fecha, motivo y persona. Un equipo de baja no se borra."""
        anterior = self.estado
        if anterior == nuevo:
            return None
        cambio = CambioEstado.objects.create(
            equipo=self, estado_anterior=anterior, estado_nuevo=nuevo,
            fecha=fecha or timezone.localdate(), motivo=motivo, usuario=usuario,
        )
        self.estado = nuevo
        self._change_reason = f"Cambio de estado: {motivo}"
        self.save(update_fields=["estado", "modificado"])
        return cambio


class PuntoCalibracion(ModeloVersionado):
    """Punto o rango a calibrar, con su EMP (RF-06, RF-07)."""

    equipo = models.ForeignKey(Equipo, on_delete=models.PROTECT, related_name="puntos")
    orden = models.PositiveSmallIntegerField("orden", default=1)
    valor_nominal = models.DecimalField("valor nominal", max_digits=14, decimal_places=6)
    emp_tipo = models.CharField("tipo de EMP", max_length=15, choices=TipoEMP.choices, default=TipoEMP.FIJO)
    emp_valor = models.DecimalField("EMP", max_digits=14, decimal_places=6, validators=[MinValueValidator(0)],
                                    help_text="Valor fijo en la unidad del equipo, o porcentaje.")
    activo = models.BooleanField("activo", default=True)

    class Meta:
        verbose_name = "punto de calibración"
        verbose_name_plural = "puntos de calibración"
        ordering = ["equipo", "orden", "valor_nominal"]

    def __str__(self):
        return f"{self.valor_nominal.normalize():f} {self.equipo.unidad} (EMP {self.emp_texto})"

    @property
    def emp_texto(self):
        v = f"{self.emp_valor.normalize():f}"
        return {TipoEMP.FIJO: f"±{v}", TipoEMP.PCT_LECTURA: f"±{v} % de la lectura",
                TipoEMP.PCT_ALCANCE: f"±{v} % del alcance"}[self.emp_tipo]


class CambioEstado(ModeloVersionado):
    equipo = models.ForeignKey(Equipo, on_delete=models.PROTECT, related_name="cambios_estado")
    estado_anterior = models.CharField("estado anterior", max_length=20, choices=EstadoEquipo.choices)
    estado_nuevo = models.CharField("estado nuevo", max_length=20, choices=EstadoEquipo.choices)
    fecha = models.DateField("fecha")
    motivo = models.CharField("motivo", max_length=250)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="decidió", related_name="+")

    class Meta:
        verbose_name = "cambio de estado"
        verbose_name_plural = "cambios de estado"
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.get_estado_anterior_display()} → {self.get_estado_nuevo_display()}"


class TipoDocumento(models.TextChoices):
    FOTO = "foto", "Fotografía"
    MANUAL = "manual", "Manual"
    FACTURA = "factura", "Factura"
    OTRO = "otro", "Otro"


class Documento(ModeloVersionado):
    """RF-13: fotografía y otros documentos del equipo."""

    equipo = models.ForeignKey(Equipo, on_delete=models.PROTECT, related_name="documentos")
    tipo = models.CharField("tipo", max_length=10, choices=TipoDocumento.choices, default=TipoDocumento.OTRO)
    titulo = models.CharField("título", max_length=150)
    archivo = models.FileField("archivo", upload_to=ruta_documento)
    subido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        verbose_name = "documento"
        verbose_name_plural = "documentos"
        ordering = ["-creado"]

    def __str__(self):
        return self.titulo


