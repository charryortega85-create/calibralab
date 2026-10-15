from django import forms

from apps.catalogos.models import Proveedor
from apps.core.formularios import FechaInput, MotivoMixin
from apps.equipos.forms import activos_o_actual
from apps.equipos.models import Equipo, EstadoEquipo

from .models import ItemPlan, Lote, PlanAnual


class LoteForm(MotivoMixin, forms.ModelForm):
    class Meta:
        model = Lote
        fields = ["codigo", "nombre", "trabajos", "proveedor", "costo_estimado", "equipos", "activo"]
        widgets = {"trabajos": forms.Textarea(attrs={"rows": 3}),
                   "equipos": forms.SelectMultiple(attrs={"size": 12})}
        help_texts = {"equipos": "Mantén presionada la tecla Ctrl (Cmd en Mac) para elegir varios.",
                      "costo_estimado": "En guaraníes, sin puntos."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proveedor"].queryset = activos_o_actual(Proveedor.objects.all(), self.instance.proveedor_id)
        self.fields["equipos"].queryset = Equipo.objects.exclude(estado=EstadoEquipo.BAJA)
        if not self.instance.pk:
            self.fields.pop("activo")

    def clean_codigo(self):
        return self.cleaned_data["codigo"].strip().upper()


class PlanForm(MotivoMixin, forms.ModelForm):
    class Meta:
        model = PlanAnual
        fields = ["ejercicio", "descripcion"]


class ItemPlanForm(MotivoMixin, forms.ModelForm):
    class Meta:
        model = ItemPlan
        fields = ["lote", "mes_previsto", "monto_previsto"]

    def __init__(self, *args, plan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.plan = plan
        lotes = Lote.objects.filter(activo=True)
        if plan and not self.instance.pk:
            lotes = lotes.exclude(items_plan__plan=plan)
        self.fields["lote"].queryset = lotes | Lote.objects.filter(pk=self.instance.lote_id)
        if self.instance.pk:
            self.fields["lote"].disabled = True


class EjecucionForm(MotivoMixin, forms.ModelForm):
    """RF-31: proveedor, estado de ejecución, estado de pago y n.º de nota de requerimiento."""

    class Meta:
        model = ItemPlan
        fields = ["proveedor", "estado_ejecucion", "nota_requerimiento", "fecha_ejecucion", "estado_pago", "monto_pagado"]
        widgets = {"fecha_ejecucion": FechaInput()}
        help_texts = {"estado_pago": "Solo para seguimiento: el sistema no gestiona pagos ni facturas."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proveedor"].queryset = activos_o_actual(Proveedor.objects.all(), self.instance.proveedor_id)

    def clean(self):
        d = super().clean()
        if d.get("estado_pago") == "pagado" and not d.get("monto_pagado"):
            self.add_error("monto_pagado", "Si está pagado, escribe el monto pagado.")
        if d.get("estado_ejecucion") == "ejecutado" and not d.get("fecha_ejecucion"):
            self.add_error("fecha_ejecucion", "Si está ejecutado, indica la fecha de ejecución.")
        return d
