from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.core.modelos import ModeloVersionado
from apps.equipos.models import TipoEMP

from . import calculos


class TipoServicio(models.TextChoices):
    CALIBRACION = "calibracion", "Calibración"
    CALIFICACION = "calificacion", "Calificación"
    CERTIFICACION = "certificacion", "Certificación"


class Resultado(models.TextChoices):
    """En los registros se guarda «conforme» / «no conforme»; en calibraciones se muestra apto / no apto."""

    CONFORME = "conforme", "Conforme"
    NO_CONFORME = "no_conforme", "No conforme"


class ReglaComparacion(models.TextChoices):
    SIMPLE = calculos.Regla.SIMPLE, "Simple: el error no supera el EMP"
    INCERTIDUMBRE = calculos.Regla.INCERTIDUMBRE, "Con incertidumbre: error + incertidumbre no supera el EMP"


def ruta_certificado(instancia, nombre):
    return f"equipos/{instancia.equipo.codigo}/certificados/{instancia.fecha:%Y-%m-%d}_{nombre}"


class Servicio(ModeloVersionado):
    """RF-15: cada calibración, calificación o certificación que recibe un equipo."""

    equipo = models.ForeignKey("equipos.Equipo", on_delete=models.PROTECT, related_name="servicios")
    tipo = models.CharField("tipo de servicio", max_length=15, choices=TipoServicio.choices,
                            default=TipoServicio.CALIBRACION)
    fecha = models.DateField("fecha de ejecución")
    proveedor = models.ForeignKey("catalogos.Proveedor", on_delete=models.PROTECT, verbose_name="proveedor")
    numero_certificado = models.CharField("n.º de certificado", max_length=60)
    certificado = models.FileField("archivo del certificado", upload_to=ruta_certificado, blank=True)
    trazabilidad = models.CharField("trazabilidad declarada", max_length=250, blank=True,
                                    help_text="Patrón o laboratorio al que remite el certificado.")
    ajustes = models.TextField("ajustes realizados", blank=True)
    observaciones = models.TextField("observaciones", blank=True)
    # Calibración (RF-17 a RF-19)
    regla = models.CharField("regla de comparación", max_length=15, choices=ReglaComparacion.choices,
                             default=ReglaComparacion.SIMPLE)
    # Resultado: calculado en calibraciones (RN-04), registrado por una persona en el resto (RF-20)
    resultado = models.CharField("resultado", max_length=12, choices=Resultado.choices, blank=True)
    # Calificación y certificación (RF-20)
    criterios_aceptacion = models.TextField("criterios de aceptación", blank=True)
    vigencia_hasta = models.DateField("vigente hasta", null=True, blank=True)
    # Próxima fecha (RN-02, RF-21)
    proxima_fecha_calculada = models.DateField("próxima fecha calculada", null=True, blank=True)
    proxima_fecha = models.DateField("próxima calibración", null=True, blank=True)
    justificacion_proxima = models.CharField("justificación del cambio de fecha", max_length=250, blank=True)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+",
                                       verbose_name="registrado por")

    class Meta:
        verbose_name = "servicio"
        verbose_name_plural = "servicios"
        ordering = ["-fecha", "-id"]
        indexes = [models.Index(fields=["equipo", "tipo", "resultado", "-fecha"])]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.numero_certificado} · {self.equipo.codigo}"

    def get_absolute_url(self):
        return reverse("servicios:detalle", args=[self.pk])

    @property
    def es_calibracion(self):
        return self.tipo == TipoServicio.CALIBRACION

    @property
    def conforme(self):
        return self.resultado == Resultado.CONFORME

    @property
    def dictamen(self):
        """Texto para mostrar: apto / no apto en calibraciones, conforme / no conforme en el resto."""
        if not self.resultado:
            return "Sin resultado"
        if self.es_calibracion:
            return "Apto" if self.conforme else "No apto"
        return self.get_resultado_display()

    def recalcular(self, proxima_manual=None, justificacion=""):
        """
        Calcula el error de cada punto, el dictamen (RN-04) y la próxima fecha (RN-02).
        Guarda la regla y el EMP usados en cada punto, aunque luego cambien en la ficha (RN-06).
        """
        if not self.es_calibracion:
            return
        alcance = self.equipo.capacidad
        resultados = []
        for p in self.puntos.all():
            r = calculos.evaluar_punto(
                referencia=p.valor_referencia, leido=p.valor_leido, informado=p.error_informado,
                incertidumbre=p.incertidumbre, emp_tipo=p.emp_tipo, emp_valor=p.emp_valor,
                alcance=alcance, regla=self.regla,
            )
            p.error, p.emp_aplicado, p.cumple = r.error, r.emp, r.cumple
            p.save(update_fields=["error", "emp_aplicado", "cumple", "modificado"])
            resultados.append(r)
        apto = calculos.es_apto(resultados)
        self.resultado = Resultado.CONFORME if apto else Resultado.NO_CONFORME
        if apto:
            self.proxima_fecha_calculada = calculos.proxima_fecha(self.fecha, self.equipo.intervalo_meses)
            if proxima_manual and proxima_manual != self.proxima_fecha_calculada:
                self.proxima_fecha, self.justificacion_proxima = proxima_manual, justificacion
            else:
                self.proxima_fecha, self.justificacion_proxima = self.proxima_fecha_calculada, ""
        else:
            # Un no apto no da fecha nueva: vale la de la última calibración conforme.
            self.proxima_fecha_calculada = self.proxima_fecha = None
            self.justificacion_proxima = ""
        self.save()

    def ultima_conforme_anterior(self):
        """Calibración conforme anterior a esta: desde ahí pudo estar fuera de tolerancia (RN-05)."""
        return (Servicio.objects.filter(equipo=self.equipo, tipo=TipoServicio.CALIBRACION,
                                        resultado=Resultado.CONFORME)
                .filter(models.Q(fecha__lt=self.fecha) | models.Q(fecha=self.fecha, pk__lt=self.pk))
                .order_by("-fecha", "-pk").first())


class PuntoMedido(ModeloVersionado):
    """RF-17: un punto calibrado con sus valores, y el EMP y el resultado de ese punto (RF-18)."""

    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name="puntos")
    orden = models.PositiveSmallIntegerField("orden", default=1)
    valor_referencia = models.DecimalField("valor de referencia", max_digits=14, decimal_places=6)
    valor_leido = models.DecimalField("valor que marcó el equipo", max_digits=14, decimal_places=6, null=True, blank=True)
    error_informado = models.DecimalField("error informado en el certificado", max_digits=14, decimal_places=6,
                                          null=True, blank=True)
    incertidumbre = models.DecimalField("incertidumbre (U)", max_digits=14, decimal_places=6, null=True, blank=True)
    # Copia del EMP de la ficha en el momento de calibrar (RN-06)
    emp_tipo = models.CharField("tipo de EMP", max_length=15, choices=TipoEMP.choices)
    emp_valor = models.DecimalField("EMP", max_digits=14, decimal_places=6)
    # Resultado calculado
    emp_aplicado = models.DecimalField("EMP aplicado", max_digits=14, decimal_places=6, null=True, blank=True)
    error = models.DecimalField("error", max_digits=14, decimal_places=6, null=True, blank=True)
    cumple = models.BooleanField("cumple", null=True)

    class Meta:
        verbose_name = "punto medido"
        verbose_name_plural = "puntos medidos"
        ordering = ["servicio", "orden", "valor_referencia"]

    def __str__(self):
        return f"Punto {self.valor_referencia.normalize():f}"


class Decision(models.TextChoices):
    FUERA_DE_SERVICIO = "fuera_servicio", "Pasar a «fuera de servicio»"
    MANTENER = "mantener", "Mantener el estado actual"


class DecisionNoApto(ModeloVersionado):
    """RN-05 / RF-22: el sistema propone y una persona decide qué hacer con un equipo no apto."""

    servicio = models.OneToOneField(Servicio, on_delete=models.PROTECT, related_name="decision")
    decision = models.CharField("decisión", max_length=15, choices=Decision.choices,
                                default=Decision.FUERA_DE_SERVICIO)
    justificacion = models.CharField("justificación", max_length=250, blank=True,
                                     help_text="Obligatoria si se mantiene el estado del equipo.")
    fuera_tolerancia_desde = models.DateField("pudo estar fuera de tolerancia desde", null=True, blank=True)
    decidido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+",
                                     verbose_name="decidió")

    class Meta:
        verbose_name = "decisión ante un no apto"
        verbose_name_plural = "decisiones ante un no apto"

    def __str__(self):
        return f"{self.get_decision_display()} · {self.servicio}"
