from django import forms
from django.forms import inlineformset_factory

from apps.catalogos.models import Area, Marca, Ubicacion, Unidad
from apps.core.formularios import FechaInput, MotivoMixin
from apps.cuentas.models import Usuario

from .models import CambioEstado, Documento, Equipo, EstadoEquipo, PuntoCalibracion, TipoEMP


def activos_o_actual(qs, actual_id):
    """Las listas ofrecen solo valores activos, más el que ya tiene el registro."""
    return qs.filter(activo=True) | qs.filter(pk=actual_id) if actual_id else qs.filter(activo=True)


class EquipoForm(MotivoMixin, forms.ModelForm):
    # RNF-16: el formulario sigue los grupos de la ficha.
    grupos = [
        ("Identificación", ["codigo", "patrimonio", "descripcion", "marca", "modelo", "numero_serie",
                            "area", "ubicacion", "responsable", "asignado_a"]),
        ("Ficha técnica", ["unidad", "rango_min", "rango_max", "resolucion", "capacidad", "tolerancia",
                           "criticidad", "intervalo_meses"]),
        ("Otros datos", ["observaciones", "motivo"]),
    ]

    class Meta:
        model = Equipo
        fields = ["codigo", "patrimonio", "descripcion", "marca", "modelo", "numero_serie", "area", "ubicacion",
                  "responsable", "asignado_a", "unidad", "rango_min", "rango_max", "resolucion", "capacidad",
                  "tolerancia", "criticidad", "intervalo_meses", "observaciones"]
        widgets = {"observaciones": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        i = self.instance
        # Cada usuario elige entre sus áreas; si hay áreas cargadas, el área es obligatoria.
        areas = Area.objects.select_related("laboratorio")
        if usuario is not None and not usuario.ve_todas_las_areas:
            areas = areas.filter(pk__in=usuario.areas_permitidas())
        self.fields["area"].queryset = activos_o_actual(areas, i.area_id)
        self.fields["area"].required = Area.objects.exists()
        self.fields["marca"].queryset = activos_o_actual(Marca.objects.all(), i.marca_id)
        self.fields["ubicacion"].queryset = activos_o_actual(Ubicacion.objects.all(), i.ubicacion_id)
        self.fields["unidad"].queryset = activos_o_actual(Unidad.objects.all(), i.unidad_id)
        self.fields["responsable"].queryset = Usuario.objects.filter(is_active=True).exclude(rol="consulta") | (
            Usuario.objects.filter(pk=i.responsable_id) if i.responsable_id else Usuario.objects.none())
        asignable = Equipo.objects.exclude(estado=EstadoEquipo.BAJA)
        if usuario is not None:
            from .acceso import equipos_visibles

            asignable = equipos_visibles(usuario, asignable)
        self.fields["asignado_a"].queryset = asignable.exclude(pk=i.pk) if i.pk else asignable

    def clean_codigo(self):
        return self.cleaned_data["codigo"].strip().upper()

    def clean(self):
        datos = super().clean()
        mn, mx = datos.get("rango_min"), datos.get("rango_max")
        if mn is not None and mx is not None and mn > mx:
            self.add_error("rango_max", "El rango «hasta» debe ser mayor o igual que el rango «desde».")
        return datos

    def grupos_de_campos(self):
        return [(t, [self[c] for c in campos if c in self.fields]) for t, campos in self.grupos]


class PuntoForm(forms.ModelForm):
    class Meta:
        model = PuntoCalibracion
        fields = ["orden", "valor_nominal", "emp_tipo", "emp_valor", "activo"]


class PuntosBaseFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        capacidad = self.instance.capacidad
        con_datos = [f for f in self.forms if f.cleaned_data and f.cleaned_data.get("valor_nominal") is not None]
        for f in con_datos:
            if f.cleaned_data.get("emp_tipo") == TipoEMP.PCT_ALCANCE and not capacidad:
                f.add_error("emp_tipo", "Para usar «% del alcance», carga la capacidad o alcance del equipo.")


PuntosFormSet = inlineformset_factory(
    Equipo, PuntoCalibracion, form=PuntoForm, formset=PuntosBaseFormSet, extra=3, can_delete=False,
)


class CambioEstadoForm(forms.ModelForm):
    confirmo = forms.BooleanField(
        label="Confirmo el cambio de estado", required=True,
        help_text="Queda registrado con la fecha, el motivo y tu nombre.",
    )

    class Meta:
        model = CambioEstado
        fields = ["estado_nuevo", "fecha", "motivo"]
        widgets = {"fecha": FechaInput()}
        labels = {"estado_nuevo": "Nuevo estado"}

    def __init__(self, *args, equipo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.equipo = equipo
        self.fields["estado_nuevo"].choices = [c for c in EstadoEquipo.choices if c[0] != equipo.estado]

    def clean_fecha(self):
        from django.utils import timezone

        fecha = self.cleaned_data["fecha"]
        if fecha > timezone.localdate():
            raise forms.ValidationError("La fecha no puede ser futura.")
        return fecha


class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = ["tipo", "titulo", "archivo"]

    def clean_archivo(self):
        from apps.core.archivos import validar_adjunto

        return validar_adjunto(self.cleaned_data["archivo"])


class ImportarForm(forms.Form):
    archivo = forms.FileField(
        label="Archivo de Excel o CSV",
        help_text="Usa la plantilla: una fila por equipo. Se revisan todas las filas antes de guardar.",
    )
    crear_faltantes = forms.BooleanField(
        label="Agregar lo que no exista: marcas, ubicaciones, unidades, laboratorios y áreas", required=False,
        help_text="Se agrega recién al guardar los equipos. Si no la marcas, cada nombre debe estar ya cargado.",
    )

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not (usuario and usuario.es_administrador):  # las listas solo las cambia el administrador
            self.fields.pop("crear_faltantes")

    def clean_archivo(self):
        a = self.cleaned_data["archivo"]
        if not a.name.lower().endswith((".csv", ".xlsx")):
            raise forms.ValidationError("El archivo debe ser .xlsx (Excel) o .csv.")
        return a
