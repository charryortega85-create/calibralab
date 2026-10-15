from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm

from .models import Configuracion, Usuario


class UsuarioCreacionAdminForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = Usuario
        fields = ("username", "nombre", "email", "rol")


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    add_form = UsuarioCreacionAdminForm
    list_display = ("username", "nombre", "email", "rol", "is_active")
    list_filter = ("rol", "is_active")
    search_fields = ("username", "nombre", "email")
    ordering = ("nombre",)
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Datos personales", {"fields": ("nombre", "email")}),
        ("Rol y estado", {"fields": ("rol", "is_active", "is_staff", "is_superuser")}),
    )
    add_fieldsets = ((None, {"fields": ("username", "nombre", "email", "rol", "password1", "password2")}),)

    def has_delete_permission(self, request, obj=None):
        return False  # RF-03 y RN-07: un usuario se desactiva, no se borra.


admin.site.register(Configuracion)
