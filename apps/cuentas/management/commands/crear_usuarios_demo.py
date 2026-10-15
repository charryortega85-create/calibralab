"""Crea los usuarios inventados de la demostración (II.1.7: solo datos de ejemplo)."""
from django.core.management.base import BaseCommand

from apps.cuentas.models import Configuracion, Rol, Usuario

USUARIOS = [
    ("mperez", "María Pérez", "mperez@lab.example", Rol.ADMINISTRADOR),
    ("lgimenez", "Lucía Giménez", "lgimenez@lab.example", Rol.TECNICO),
    ("cbenitez", "Carlos Benítez", "cbenitez@lab.example", Rol.TECNICO),
    ("aduarte", "Andrés Duarte", "aduarte@lab.example", Rol.TECNICO),
    ("auditor", "Ana Auditora", "auditor@lab.example", Rol.CONSULTA),
]


class Command(BaseCommand):
    help = "Crea los usuarios de ejemplo de la demostración, todos con la misma contraseña."

    def add_arguments(self, parser):
        parser.add_argument("--contrasena", default="Calibra-2026", help="Contraseña para todos (mín. 10 caracteres).")

    def handle(self, *args, contrasena, **opciones):
        Configuracion.actual()
        for username, nombre, email, rol in USUARIOS:
            usuario, creado = Usuario.objects.get_or_create(
                username=username, defaults={"nombre": nombre, "email": email, "rol": rol}
            )
            if creado:
                usuario.set_password(contrasena)
                if rol == Rol.ADMINISTRADOR:
                    usuario.is_staff = usuario.is_superuser = True
                usuario.save()
            self.stdout.write(f"{'Creado' if creado else 'Ya existía'}: {username} ({usuario.get_rol_display()})")
        self.stdout.write(self.style.SUCCESS(f"Listo. Contraseña de los usuarios nuevos: {contrasena}"))
