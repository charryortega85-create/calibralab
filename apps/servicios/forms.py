from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from apps.catalogos.models import Proveedor
from apps.core.archivos import validar_adjunto
from apps.core.formularios import FechaInput, MotivoMixin
from apps.equipos.forms import activos_o_actual

from .models import (AnexoServicio, Decision, DecisionNoApto, PatronUtilizado, PuntoMedido, ReglaComparacion, Servicio,
                     TipoServicio)


class ServicioForm(MotivoMixin, forms.ModelForm):
    proxima_manual = forms.DateField(
        label="Cambiar la próxima fecha", required=False, widget=FechaInput(),
        help_text="Déjalo vacío para usar la fecha calculada (última conforme + intervalo).",
    )

    grupos = [
        ("Servicio", ["tipo", "fecha", "proveedor", "numero_certificado", "certificado", "trazabilidad"], ""),
        ("Calibración", ["regla", "proxima_manual", "justificacion_proxima"], "calibracion"),
        ("Calificación o certificación", ["resultado", "criterios_aceptacion", "vigencia_hasta"], "otro"),
        ("Datos del certificado", ["lugar", "temperatura_ambiente", "humedad_relativa", "procedimiento",
                                   "realizado_por", "autorizado_por"], "certificado"),
        ("Otros datos", ["ajustes", "observaciones", "motivo"], ""),
    ]

    class Meta:
        model = Servicio
        fields = ["tipo", "fecha", "proveedor", "numero_certificado", "certificado", "trazabilidad", "regla",
                  "justificacion_proxima", "resultado", "criterios_aceptacion", "vigencia_hasta", "lugar",
                  "temperatura_ambiente", "humedad_relativa", "procedimiento", "realizado_por", "autorizado_por",
                  "ajustes", "observaciones"]
        widgets = {
            "fecha": FechaInput(), "vigencia_hasta": FechaInput(),
            "ajustes": forms.Textarea(attrs={"rows": 2}), "observaciones": forms.Textarea(attrs={"rows": 2}),
            "criterios_aceptacion": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {"resultado": "Resultado (lo registra una persona)"}

    def __init__(self, *args, equipo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.equipo = equipo
        self.fields["proveedor"].queryset = activos_o_actual(Proveedor.objects.all(), self.instance.proveedor_id)
        self.fields["regla"].required = False  # solo se usa en calibraciones
        if self.instance.pk:
            self.fields["tipo"].disabled = True
            if self.instance.proxima_fecha and self.instance.proxima_fecha != self.instance.proxima_fecha_calculada:
                self.initial["proxima_manual"] = self.instance.proxima_fecha

    def clean_fecha(self):
        fecha = self.cleaned_data["fecha"]
        if fecha > timezone.localdate():
            raise forms.ValidationError("La fecha de ejecución no puede ser futura.")
        return fecha

    def clean_certificado(self):
        return validar_adjunto(self.cleaned_data.get("certificado"))

    def clean(self):
        d = super().clean()
        tipo = d.get("tipo") or self.instance.tipo
        d["regla"] = d.get("regla") or ReglaComparacion.SIMPLE
        if tipo == TipoServicio.CALIBRACION:
            # RN-08: proveedor, n.º de certificado y archivo son obligatorios en una calibración.
            if not d.get("certificado") and not self.instance.certificado:
                self.add_error("certificado", "En una calibración el archivo del certificado es obligatorio (RN-08).")
            if d.get("proxima_manual") and not d.get("justificacion_proxima", "").strip():
                self.add_error("justificacion_proxima", "Para cambiar la próxima fecha escribe la justificación (RN-02).")
            if d.get("proxima_manual") and d.get("fecha") and d["proxima_manual"] <= d["fecha"]:
                self.add_error("proxima_manual", "La próxima fecha debe ser posterior a la fecha de ejecución.")
            d["resultado"] = self.instance.resultado or ""
            d["vigencia_hasta"] = None
        else:
            if not d.get("resultado"):
                self.add_error("resultado", "Indica si el resultado fue conforme o no conforme (RF-20).")
            if not d.get("vigencia_hasta"):
                self.add_error("vigencia_hasta", "Indica hasta cuándo es válida (RF-20).")
            elif d.get("fecha") and d["vigencia_hasta"] <= d["fecha"]:
                self.add_error("vigencia_hasta", "La vigencia debe terminar después de la fecha de ejecución.")
            d["proxima_manual"] = None
        return d

    def grupos_de_campos(self):
        return [(t, [self[c] for c in campos if c in self.fields], clase) for t, campos, clase in self.grupos]


class PuntoMedidoForm(forms.ModelForm):
    class Meta:
        model = PuntoMedido
        fields = ["valor_referencia", "valor_leido", "error_informado", "incertidumbre"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["valor_referencia"].required = False

    def tiene_datos(self):
        d = getattr(self, "cleaned_data", {}) or {}
        return any(d.get(c) is not None for c in ("valor_leido", "error_informado"))

    def clean(self):
        d = super().clean()
        if d.get("valor_leido") is not None and d.get("error_informado") is not None:
            self.add_error("error_informado", "Escribe el valor leído o el error informado, no los dos.")
        if self.tiene_datos() and d.get("valor_referencia") is None:
            self.add_error("valor_referencia", "Falta el valor de referencia.")
        return d


class PuntosMedidosFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        if not any(f.tiene_datos() for f in self.forms):
            raise forms.ValidationError(
                "Escribe, al menos en un punto, el valor que marcó el equipo o el error que informa el certificado."
            )


PuntosFormSet = inlineformset_factory(
    Servicio, PuntoMedido, form=PuntoMedidoForm, formset=PuntosMedidosFormSet, extra=0, can_delete=False,
)


class PatronForm(forms.ModelForm):
    class Meta:
        model = PatronUtilizado
        fields = ["identificacion", "descripcion", "certificado", "proxima_calibracion"]
        widgets = {"proxima_calibracion": forms.TextInput(attrs={"placeholder": "AAAA-MM"})}


def patrones_formset(extra):
    """Patrones del certificado. No se borran (RN-07): una fila mal cargada se corrige."""
    return inlineformset_factory(Servicio, PatronUtilizado, form=PatronForm, extra=extra, can_delete=False)


class AnexoForm(forms.ModelForm):
    class Meta:
        model = AnexoServicio
        fields = ["titulo", "archivo"]

    def clean_archivo(self):
        return validar_adjunto(self.cleaned_data.get("archivo"), obligatorio=True)


class DecisionForm(forms.ModelForm):
    class Meta:
        model = DecisionNoApto
        fields = ["decision", "justificacion"]
        widgets = {"decision": forms.RadioSelect}

    def clean(self):
        d = super().clean()
        if d.get("decision") == Decision.MANTENER and not d.get("justificacion", "").strip():
            self.add_error("justificacion", "Si el equipo no pasa a «fuera de servicio», escribe por qué.")
        return d


class ElegirEquipoForm(forms.Form):
    equipo = forms.ModelChoiceField(queryset=None, label="Equipo")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.equipos.models import Equipo, EstadoEquipo

        self.fields["equipo"].queryset = Equipo.objects.exclude(estado=EstadoEquipo.BAJA)
