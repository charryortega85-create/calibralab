from django.apps import AppConfig


class MantenimientoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.mantenimiento"
    verbose_name = "Mantenimiento y novedades"

    def ready(self):
        from apps.auditoria.registro import auditar

        from .models import EvaluacionEfecto, Novedad, PlanMantenimiento

        excluir = {"creado", "modificado"}
        auditar(PlanMantenimiento, excluir=excluir, campos_estado={"activo"}, equipo=lambda p: p.equipo.codigo)
        auditar(Novedad, excluir=excluir, equipo=lambda n: n.equipo.codigo)
        auditar(EvaluacionEfecto, excluir=excluir, equipo=lambda e: e.servicio.equipo.codigo)
