from django import forms
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm

from .models import Configuracion, Usuario


class IngresoForm(AuthenticationForm):
    error_messages = {
        "invalid_login": (
            "El usuario o la contraseña no son correctos. Revisa los datos e inténtalo de nuevo; "
            "tras 5 intentos fallidos seguidos el acceso se bloquea 15 minutos."
        ),
        "inactive": "Este usuario está desactivado. Pide al administrador que lo active.",
    }


class UsuarioCrearForm(forms.ModelForm):
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
        fields = ["nombre", "username", "email", "rol"]
        labels = {"username": "Usuario"}
        help_texts = {"username": "Con este nombre ingresa al sistema. Sin espacios."}

    def clean(self):
        datos = super().clean()
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
        return usuario


class UsuarioEditarForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ["nombre", "email", "rol", "is_active"]
        labels = {"is_active": "Activo"}
        help_texts = {"is_active": "Un usuario desactivado no puede ingresar, pero su nombre se conserva en los historiales."}

    def __init__(self, *args, editor=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Un administrador no puede quitarse a sí mismo el rol ni desactivarse: se quedaría sin acceso.
        if editor is not None and editor.pk == self.instance.pk:
            self.fields["rol"].disabled = True
            self.fields["is_active"].disabled = True


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
