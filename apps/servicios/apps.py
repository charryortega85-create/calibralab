from django.apps import AppConfig


class ServiciosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.servicios"
    verbose_name = "Calibraciones, calificaciones y certificaciones"

    def ready(self):
        from apps.auditoria.registro import auditar

        from .models import AnexoServicio, DecisionNoApto, PatronUtilizado, PuntoMedido, Servicio

        excluir = {"creado", "modificado"}
        auditar(Servicio, excluir=excluir, equipo=lambda s: s.equipo.codigo)
        auditar(PuntoMedido, excluir=excluir | {"emp_aplicado", "error", "cumple"},
                equipo=lambda p: p.servicio.equipo.codigo)
        auditar(DecisionNoApto, excluir=excluir, equipo=lambda d: d.servicio.equipo.codigo)
        auditar(PatronUtilizado, excluir=excluir, equipo=lambda p: p.servicio.equipo.codigo)
        auditar(AnexoServicio, excluir=excluir, equipo=lambda a: a.servicio.equipo.codigo)
