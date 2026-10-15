from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.auditoria"
    verbose_name = "Registro de cambios"

    def ready(self):
        from . import senales  # noqa: F401  (conecta las señales del registro de cambios)
