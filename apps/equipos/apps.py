from django.apps import AppConfig


class EquiposConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.equipos"
    verbose_name = "Inventario y ficha del equipo"

    def ready(self):
        from apps.auditoria.registro import auditar

        from .models import CambioEstado, Documento, Equipo, PuntoCalibracion

        excluir = {"creado", "modificado"}
        auditar(Equipo, excluir=excluir, campos_estado={"estado"}, equipo=lambda e: e.codigo)
        auditar(PuntoCalibracion, excluir=excluir, equipo=lambda p: p.equipo.codigo)
        auditar(CambioEstado, excluir=excluir, equipo=lambda c: c.equipo.codigo)
        auditar(Documento, excluir=excluir, equipo=lambda d: d.equipo.codigo)
