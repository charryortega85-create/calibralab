from django import forms
from django.db.models import Q
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm

from .models import Configuracion, Rol, Usuario


class IngresoForm(AuthenticationForm):
    error_messages = {
        "invalid_login": (
            "El usuario o la contraseña no son correctos. Revisa los datos e inténtalo de nuevo; "
            "tras 5 intentos fallidos seguidos el acceso se bloquea 15 minutos."
        ),
        "inactive": "Este usuario está desactivado. Pide al administrador que lo active.",
    }


class AreasMixin:
    """
    Los laboratorios a cargo (Encargado) y las áreas (Técnico) de la persona.

    Si quien edita es un Encargado de laboratorio, solo crea o edita técnicos, y solo con
    áreas de sus laboratorios; las áreas que el técnico tenga en otros laboratorios se conservan.
    """

    def _preparar_areas(self, editor=None):
        from apps.catalogos.models import Area, Laboratorio

        self.editor = editor
        for campo, modelo, qs in (("laboratorios", Laboratorio, Laboratorio.objects.all()),
                                  ("areas", Area, Area.objects.select_related("laboratorio"))):
            if not modelo.objects.exists():
                self.fields.pop(campo)
                continue
            actuales = getattr(self.instance, campo).all() if self.instance.pk else modelo.objects.none()
            self.fields[campo].queryset = qs.filter(Q(activo=True) | Q(pk__in=actuales))
        if self.es_encargado:
            self.fields.pop("laboratorios", None)
            self.fields["rol"].choices = [(Rol.TECNICO, Rol.TECNICO.label)]
            self.fields["rol"].initial = Rol.TECNICO
            if "areas" in self.fields:
                self.fields["areas"].queryset = editor.areas_permitidas().filter(activo=True).select_related("laboratorio")
                self.fields["areas"].required = True
                self.fields["areas"].help_text = "Las áreas de tus laboratorios en las que trabaja."

    @property
    def es_encargado(self):
        return self.editor is not None and self.editor.es_encargado

    def _limpiar_areas(self, datos):
        rol = datos.get("rol")
        if self.es_encargado:
            if "areas" not in self.fields:
                raise forms.ValidationError("Tus laboratorios todavía no tienen áreas. Agrega una en Laboratorios y áreas.")
            otras = self.instance.areas.exclude(pk__in=self.editor.areas_permitidas()) if self.instance.pk else []
            datos["areas"] = list(datos.get("areas") or []) + list(otras)
            return datos
        if rol == Rol.ENCARGADO:
            if "laboratorios" in self.fields and not datos.get("laboratorios"):
                self.add_error("laboratorios", "Marca al menos un laboratorio a su cargo.")
            datos["areas"] = []
        else:
            datos["laboratorios"] = []
        return datos


class UsuarioCrearForm(AreasMixin, forms.ModelForm):
    password1 = forms.CharField(
        label="Contraseña inicial",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Al menos 10 caracteres. La persona puede cambiarla después desde su perfil.",
    )
    password2 = forms.CharField(
        label="Repite la contraseña",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = Usuario
        fields = ["nombre", "username", "email", "rol", "laboratorios", "areas"]
        labels = {"username": "Usuario"}
        widgets = {"laboratorios": forms.CheckboxSelectMultiple, "areas": forms.CheckboxSelectMultiple}
        help_texts = {"username": "Con este nombre ingresa al sistema. Sin espacios."}

    def __init__(self, *args, editor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._preparar_areas(editor)

    def clean(self):
        datos = self._limpiar_areas(super().clean())
        p1, p2 = datos.get("password1"), datos.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las dos contraseñas no coinciden. Escríbelas de nuevo.")
        if p1:
            from django.contrib.auth.password_validation import validate_password

            try:
                validate_password(p1, Usuario(username=datos.get("username"), email=datos.get("email")))
            except forms.ValidationError as e:
                self.add_error("password1", e)
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data["password1"])
        if commit:
            usuario.save()
            self.save_m2m()
        return usuario


class UsuarioEditarForm(AreasMixin, forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ["nombre", "email", "rol", "laboratorios", "areas", "is_active"]
        widgets = {"laboratorios": forms.CheckboxSelectMultiple, "areas": forms.CheckboxSelectMultiple}
        labels = {"is_active": "Activo"}
        help_texts = {"is_active": "Un usuario desactivado no puede ingresar, pero su nombre se conserva en los historiales."}

    def __init__(self, *args, editor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._preparar_areas(editor)
        # Un administrador no puede quitarse a sí mismo el rol ni desactivarse: se quedaría sin acceso.
        if editor is not None and editor.pk == self.instance.pk:
            self.fields["rol"].disabled = True
            self.fields["is_active"].disabled = True

    def clean(self):
        return self._limpiar_areas(super().clean())


class RestablecerContrasenaForm(SetPasswordForm):
    pass


class ConfiguracionForm(forms.ModelForm):
    class Meta:
        model = Configuracion
        fields = ["plazo_aviso_dias", "hora_envio"]
        widgets = {"hora_envio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M")}

    def clean_plazo_aviso_dias(self):
        dias = self.cleaned_data["plazo_aviso_dias"]
        if not 1 <= dias <= 365:
            raise forms.ValidationError("Escribe un plazo entre 1 y 365 días.")
        return dias
