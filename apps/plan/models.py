from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum
from django.urls import reverse

from apps.core.modelos import ModeloVersionado

MESES = [(i, n) for i, n in enumerate(
    ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
     "noviembre", "diciembre"], start=1)]


class Lote(ModeloVersionado):
    """RF-29: grupo de equipos que se planifican, contratan y calibran juntos."""

    codigo = models.CharField("código", max_length=30, unique=True)
    nombre = models.CharField("nombre", max_length=150)
    trabajos = models.TextField("trabajos requeridos", help_text="Qué se pide al proveedor: calibración, calificación, puntos, etc.")
    proveedor = models.ForeignKey("catalogos.Proveedor", on_delete=models.PROTECT, null=True, blank=True,
                                  verbose_name="proveedor previsto")
    costo_estimado = models.DecimalField("costo estimado", max_digits=14, decimal_places=0, default=0,
                                         validators=[MinValueValidator(0)])
    equipos = models.ManyToManyField("equipos.Equipo", related_name="lotes", blank=True, verbose_name="equipos")
    activo = models.BooleanField("activo", default=True)

    class Meta:
        verbose_name = "lote"
        verbose_name_plural = "lotes"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"

    def get_absolute_url(self):
        return reverse("plan:lote", args=[self.pk])


class PlanAnual(ModeloVersionado):
    """RF-30: programa de calibración de un ejercicio (año)."""

    ejercicio = models.PositiveSmallIntegerField("ejercicio", unique=True,
                                                 validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    descripcion = models.CharField("descripción", max_length=200, blank=True)

    class Meta:
        verbose_name = "plan anual"
        verbose_name_plural = "planes anuales"
        ordering = ["-ejercicio"]

    def __str__(self):
        return f"Plan {self.ejercicio}"

    def get_absolute_url(self):
        return reverse("plan:plan", args=[self.pk])

    def avance(self):
        """RF-32: ejecutado frente a programado y pagado frente a previsto."""
        items = self.items.all()
        total = items.count()
        ejecutados = items.filter(estado_ejecucion=EstadoEjecucion.EJECUTADO).count()
        montos = items.aggregate(previsto=Sum("monto_previsto"), pagado=Sum("monto_pagado"))
        previsto, pagado = montos["previsto"] or Decimal(0), montos["pagado"] or Decimal(0)
        return {
            "programados": total, "ejecutados": ejecutados,
            "pct_plan": round(ejecutados * 100 / total, 1) if total else 0,
            "previsto": previsto, "pagado": pagado,
            "pct_presupuesto": round(pagado * 100 / previsto, 1) if previsto else 0,
        }


class EstadoEjecucion(models.TextChoices):
    PROGRAMADO = "programado", "Programado"
    SOLICITADO = "solicitado", "Solicitado"
    EN_EJECUCION = "en_ejecucion", "En ejecución"
    EJECUTADO = "ejecutado", "Ejecutado"
    CANCELADO = "cancelado", "Cancelado"


class EstadoPago(models.TextChoices):
    """Solo dato de seguimiento: el sistema no gestiona pagos ni facturas (RF-31)."""

    PENDIENTE = "pendiente", "Pendiente"
    PAGADO = "pagado", "Pagado"


class ItemPlan(ModeloVersionado):
    """Un lote dentro del plan anual (RF-30) y su ejecución (RF-31)."""

    plan = models.ForeignKey(PlanAnual, on_delete=models.PROTECT, related_name="items")
    lote = models.ForeignKey(Lote, on_delete=models.PROTECT, related_name="items_plan")
    mes_previsto = models.PositiveSmallIntegerField("mes previsto de contratación", choices=MESES)
    monto_previsto = models.DecimalField("monto previsto", max_digits=14, decimal_places=0,
                                         validators=[MinValueValidator(0)])
    # Ejecución (RF-31)
    proveedor = models.ForeignKey("catalogos.Proveedor", on_delete=models.PROTECT, null=True, blank=True,
                                  verbose_name="proveedor contratado")
    estado_ejecucion = models.CharField("estado de ejecución", max_length=15, choices=EstadoEjecucion.choices,
                                        default=EstadoEjecucion.PROGRAMADO)
    estado_pago = models.CharField("estado de pago", max_length=10, choices=EstadoPago.choices,
                                   default=EstadoPago.PENDIENTE)
    nota_requerimiento = models.CharField("n.º de nota de requerimiento", max_length=40, blank=True)
    fecha_ejecucion = models.DateField("fecha de ejecución", null=True, blank=True)
    monto_pagado = models.DecimalField("monto pagado", max_digits=14, decimal_places=0, default=0,
                                       validators=[MinValueValidator(0)])

    class Meta:
        verbose_name = "lote del plan"
        verbose_name_plural = "lotes del plan"
        ordering = ["plan", "mes_previsto", "lote__codigo"]
        constraints = [models.UniqueConstraint(fields=["plan", "lote"], name="plan_lote_unico")]

    def __str__(self):
        return f"{self.plan} · {self.lote.codigo}"
