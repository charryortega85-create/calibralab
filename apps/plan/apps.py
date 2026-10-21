from django.apps import AppConfig


class PlanConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.plan"
    verbose_name = "Plan, lotes y presupuesto"

    def ready(self):
        from apps.auditoria.registro import auditar

        from .models import ItemPlan, Lote, PlanAnual

        excluir = {"creado", "modificado"}
        auditar(Lote, excluir=excluir, campos_estado={"activo"})
        auditar(PlanAnual, excluir=excluir)
        auditar(ItemPlan, excluir=excluir, campos_estado={"estado_ejecucion", "estado_pago"})
