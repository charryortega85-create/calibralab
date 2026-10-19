"""
Servidor de CalibraLab para Windows (gunicorn no funciona en Windows).

Lo inicia `servidor.bat`, que se puede dejar como tarea programada para que el sistema
arranque solo con la PC. Ver la guía de instalación en Windows.
"""
import os

from waitress import serve

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.wsgi import application  # noqa: E402

if __name__ == "__main__":
    puerto = int(os.environ.get("PUERTO", "8000"))
    print(f"CalibraLab escuchando en el puerto {puerto}", flush=True)
    serve(application, host="0.0.0.0", port=puerto, threads=8)
