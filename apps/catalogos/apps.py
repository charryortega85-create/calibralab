from django.apps import AppConfig


class CatalogosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalogos"
    verbose_name = "Listas controladas"

    def ready(self):
        from apps.auditoria.registro import auditar

        from .models import Marca, Proveedor, Ubicacion, Unidad

        for modelo in (Marca, Ubicacion, Unidad, Proveedor):
            auditar(modelo, excluir={"creado", "modificado"}, campos_estado={"activo"})
