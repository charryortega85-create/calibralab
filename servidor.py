"""
Servidor de CalibraLab para Windows (gunicorn no funciona en Windows).

Lo inicia `servidor.bat`, que se puede dejar como tarea programada para que el sistema
arranque solo con la PC. Ver la guía de instalación en Windows.

Además envía los avisos por correo una vez por día, a la hora que el administrador eligió en
Configuración (RF-28), así no hace falta programar otra tarea.
"""
import os
import threading
import time

from waitress import serve

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.wsgi import application  # noqa: E402


def avisos_diarios():
    from django.db import close_old_connections
    from django.utils import timezone

    from apps.alertas.avisos import enviar_pendientes
    from apps.cuentas.models import Configuracion

    ultimo = None
    while True:
        try:
            ahora = timezone.localtime()
            if ultimo != ahora.date() and ahora.time() >= Configuracion.actual().hora_envio:
                # Si el servidor se reinicia, no se repiten: solo sale lo que todavía no se envió bien.
                enviados = enviar_pendientes()
                ultimo = ahora.date()
                print(f"{ahora:%Y-%m-%d %H:%M} avisos por correo: {len(enviados)}", flush=True)
        except Exception as exc:  # p. ej. PostgreSQL todavía no arrancó: se reintenta en un minuto
            print(f"No se pudieron enviar los avisos: {exc}", flush=True)
        finally:
            close_old_connections()
        time.sleep(60)


if __name__ == "__main__":
    puerto = int(os.environ.get("PUERTO", "8000"))
    if os.environ.get("AVISOS_AUTOMATICOS", "si").lower() not in ("no", "0", "false"):
        threading.Thread(target=avisos_diarios, daemon=True).start()
    print(f"CalibraLab escuchando en el puerto {puerto}", flush=True)
    serve(application, host="0.0.0.0", port=puerto, threads=8)
