from datetime import time

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class Rol(models.TextChoices):
    """Los tres roles del sistema (II.1.3)."""

    TECNICO = "tecnico", "Técnico"
    ADMINISTRADOR = "administrador", "Administrador"
    CONSULTA = "consulta", "Consulta"


class UsuarioManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("rol", Rol.ADMINISTRADOR)
        extra_fields.setdefault("nombre", username)
        return super().create_superuser(username, email, password, **extra_fields)


class Usuario(AbstractUser):
    """
    Persona que usa el sistema. Solo guarda nombre, usuario y correo (RNF-07).

    Un usuario no se borra: se desactiva (`is_active`), no puede ingresar y su nombre
    se conserva en los historiales (RF-03).
    """

    # RNF-07: se quitan los campos de nombre y apellido separados de Django.
    first_name = None
    last_name = None

    nombre = models.CharField("nombre y apellido", max_length=150)
    email = models.EmailField("correo electrónico", unique=True)
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.TECNICO)

    REQUIRED_FIELDS = ["email"]
    objects = UsuarioManager()

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre or self.username

    def get_full_name(self):
        return self.nombre

    def get_short_name(self):
        return self.nombre.split(" ")[0] if self.nombre else self.username

    @property
    def iniciales(self):
        partes = (self.nombre or self.username).split()
        return "".join(p[0] for p in partes[:2]).upper()

    @property
    def es_administrador(self):
        return self.rol == Rol.ADMINISTRADOR

    @property
    def puede_editar(self):
        """Técnico y Administrador crean y modifican datos; Consulta solo mira (II.1.3)."""
        return self.rol in (Rol.TECNICO, Rol.ADMINISTRADOR)


class Configuracion(models.Model):
    """
    Parámetros del sistema que define el Administrador. Hay una sola fila
    (un laboratorio por instalación, II.1.7).
    """

    plazo_aviso_dias = models.PositiveSmallIntegerField(
        "plazo de aviso (días)",
        default=30,
        help_text="Cuántos días antes del vencimiento se avisa por correo (RF-27).",
    )
    hora_envio = models.TimeField(
        "hora del envío diario",
        default=time(8, 0),
        help_text="Hora a la que salen los avisos automáticos por correo (RF-28).",
    )

    class Meta:
        verbose_name = "configuración"
        verbose_name_plural = "configuración"

    def __str__(self):
        return "Configuración del sistema"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def actual(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
