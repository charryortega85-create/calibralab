from django.apps import AppConfig


class CuentasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cuentas"
    verbose_name = "Acceso y usuarios"

    def ready(self):
        from apps.auditoria.registro import auditar

        from .models import Configuracion, Usuario

        auditar(
            Usuario,
            excluir={"last_login", "date_joined"},
            ocultar={"password"},
            campos_estado={"is_active"},
        )
        auditar(Configuracion)
