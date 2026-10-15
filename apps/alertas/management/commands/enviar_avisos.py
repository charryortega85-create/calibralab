"""
Envía los avisos de vencimiento del día (RF-28).

Se programa con cron para que corra una vez por día a la hora configurada, por ejemplo:
    0 8 * * 1-5  cd /app && python manage.py enviar_avisos
"""
from django.core.management.base import BaseCommand

from apps.alertas.avisos import enviar_pendientes
from apps.alertas.models import ResultadoEnvio


class Command(BaseCommand):
    help = "Envía por correo los avisos de calibraciones por vencer y vencidas."

    def handle(self, *args, **opciones):
        avisos = enviar_pendientes()
        errores = [a for a in avisos if a.resultado == ResultadoEnvio.ERROR]
        self.stdout.write(f"Avisos enviados: {len(avisos) - len(errores)}. Con error: {len(errores)}.")
        for a in errores:
            self.stderr.write(f"  {a.equipo.codigo} → {a.correo}: {a.detalle}")
