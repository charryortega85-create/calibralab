from django.contrib import admin

from .models import RegistroCambio


@admin.register(RegistroCambio)
class RegistroCambioAdmin(admin.ModelAdmin):
    """Solo lectura: el registro de cambios no se modifica ni se borra (RNF-12)."""

    list_display = ("fecha", "usuario_nombre", "accion", "modelo", "objeto", "campo", "valor_anterior", "valor_nuevo")
    list_filter = ("accion", "modelo")
    search_fields = ("usuario_nombre", "objeto", "equipo", "campo")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
