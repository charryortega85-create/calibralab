from django import forms
from django.contrib.auth import get_user_model

from apps.core.formularios import FechaInput, MotivoMixin

from .models import EvaluacionEfecto, Novedad, PlanMantenimiento


def _usuarios_activos(actual_id=None):
    return get_user_model().objects.filter(is_active=True) | get_user_model().objects.filter(pk=actual_id)


class PlanMantenimientoForm(MotivoMixin, forms.ModelForm):
    class Meta:
        model = PlanMantenimiento
        fields = ["actividad", "frecuencia_meses", "responsable", "activo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["responsable"].queryset = _usuarios_activos(self.instance.responsable_id)
        if not self.instance.pk:
            self.fields.pop("activo")


class NovedadForm(MotivoMixin, forms.ModelForm):
    class Meta:
        model = Novedad
        fields = ["tipo", "fecha", "descripcion", "plan", "resultado", "responsable"]
        widgets = {"fecha": FechaInput(), "descripcion": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, equipo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["responsable"].queryset = _usuarios_activos(self.instance.responsable_id)
        self.fields["plan"].queryset = PlanMantenimiento.objects.filter(equipo=equipo, activo=True)
        self.fields["plan"].required = False
        if not self.fields["plan"].queryset.exists():
            self.fields.pop("plan")


class EvaluacionForm(MotivoMixin, forms.ModelForm):
    class Meta:
        model = EvaluacionEfecto
        fields = ["desde", "hasta", "resultados_revisados", "conclusion", "acciones", "fecha"]
        widgets = {"desde": FechaInput(), "hasta": FechaInput(), "fecha": FechaInput(),
                   "resultados_revisados": forms.Textarea(attrs={"rows": 4}),
                   "acciones": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        d = super().clean()
        if d.get("desde") and d.get("hasta") and d["desde"] > d["hasta"]:
            self.add_error("hasta", "La fecha final no puede ser anterior a la inicial.")
        if d.get("conclusion") == "con_efecto" and not (d.get("acciones") or "").strip():
            self.add_error("acciones", "Si hubo efecto sobre los resultados, describe las acciones tomadas.")
        return d
