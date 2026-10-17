from django.apps import AppConfig


class CatalogosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalogos"
    verbose_name = "Listas controladas"

    def ready(self):
        from apps.auditoria.registro import auditar

        from .models import Area, Laboratorio, Marca, Proveedor, Ubicacion, Unidad

        for modelo in (Laboratorio, Area, Marca, Ubicacion, Unidad, Proveedor):
            auditar(modelo, excluir={"creado", "modificado"}, campos_estado={"activo"})
