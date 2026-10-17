from django import forms


class MotivoMixin(forms.Form):
    """
    RN-07 / RF-24: toda corrección de un registro existente pide el motivo.
    El motivo queda guardado en la versión anterior (`history_change_reason`).
    """

    motivo = forms.CharField(
        label="Motivo de la corrección",
        required=False,
        max_length=250,
        widget=forms.TextInput(attrs={"placeholder": "Por ejemplo: error de transcripción del certificado"}),
        help_text="Queda guardado junto con la versión anterior, que no se borra.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instancia = getattr(self, "instance", None)
        if instancia is None or instancia.pk is None:
            self.fields.pop("motivo")
        else:
            self.fields["motivo"].required = True
            # El motivo va al final del formulario.
            self.order_fields([f for f in self.fields if f != "motivo"] + ["motivo"])

    def save(self, commit=True):
        obj = super().save(commit=False)
        if "motivo" in self.fields:
            obj._change_reason = self.cleaned_data["motivo"]
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class FechaInput(forms.DateInput):
    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs, format="%Y-%m-%d")
