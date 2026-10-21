from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.modelos import ModeloVersionado


class PlanMantenimiento(ModeloVersionado):
    """RF-34: tareas de mantenimiento programadas de cada equipo."""

    equipo = models.ForeignKey("equipos.Equipo", on_delete=models.PROTECT, related_name="planes_mantenimiento")
    actividad = models.CharField("actividad", max_length=200)
    frecuencia_meses = models.PositiveSmallIntegerField("frecuencia (meses)", validators=[MinValueValidator(1)])
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+",
                                    verbose_name="responsable")
    activo = models.BooleanField("activo", default=True)

    class Meta:
        verbose_name = "plan de mantenimiento"
        verbose_name_plural = "planes de mantenimiento"
        ordering = ["equipo", "actividad"]

    def __str__(self):
        return f"{self.actividad} (cada {self.frecuencia_meses} meses)"


class TipoNovedad(models.TextChoices):
    MANTENIMIENTO = "mantenimiento", "Mantenimiento"
    VERIFICACION = "verificacion", "Verificación intermedia"
    DANO = "dano", "Daño"
    FALLA = "falla", "Falla"
    MODIFICACION = "modificacion", "Modificación"
    REPARACION = "reparacion", "Reparación"


class Novedad(ModeloVersionado):
    """RF-34: lo que le ocurre al equipo entre una calibración y la siguiente."""

    equipo = models.ForeignKey("equipos.Equipo", on_delete=models.PROTECT, related_name="novedades")
    tipo = models.CharField("tipo", max_length=15, choices=TipoNovedad.choices)
    fecha = models.DateField("fecha")
    descripcion = models.TextField("descripción")
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+",
                                    verbose_name="responsable")
    plan = models.ForeignKey(PlanMantenimiento, on_delete=models.PROTECT, null=True, blank=True,
                             related_name="ejecuciones", verbose_name="tarea del plan que cumple")
    resultado = models.CharField("resultado o acciones", max_length=250, blank=True)

    class Meta:
        verbose_name = "novedad"
        verbose_name_plural = "novedades"
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.equipo.codigo} · {self.fecha}"


class Conclusion(models.TextChoices):
    SIN_EFECTO = "sin_efecto", "Sin efecto sobre los resultados"
    CON_EFECTO = "con_efecto", "Con efecto: se toman acciones"


class EvaluacionEfecto(ModeloVersionado):
    """RF-35: evaluación del período fuera de tolerancia, vinculada al no apto que la originó (RN-05)."""

    servicio = models.OneToOneField("servicios.Servicio", on_delete=models.PROTECT, related_name="evaluacion",
                                    verbose_name="calibración no apta")
    desde = models.DateField("período evaluado desde", null=True, blank=True)
    hasta = models.DateField("período evaluado hasta")
    resultados_revisados = models.TextField("resultados revisados",
                                            help_text="Ensayos o informes emitidos en el período que se revisaron.")
    conclusion = models.CharField("conclusión", max_length=12, choices=Conclusion.choices)
    acciones = models.TextField("acciones tomadas", blank=True)
    evaluado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+",
                                     verbose_name="evaluado por")
    fecha = models.DateField("fecha de la evaluación")

    class Meta:
        verbose_name = "evaluación del efecto"
        verbose_name_plural = "evaluaciones del efecto"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Evaluación de {self.servicio}"
