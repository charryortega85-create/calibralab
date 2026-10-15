from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin


@login_required
def inicio(request):
    """
    Pantalla de inicio (RF-26): lo urgente al ingresar (RNF-15). Reproduce el panel de
    la maqueta con los datos reales.
    """
    from .panel import datos

    ahora = timezone.localtime()
    saludo = "Buenos días" if ahora.hour < 12 else "Buenas tardes" if ahora.hour < 19 else "Buenas noches"
    filtro = request.GET.get("servicios", "todos")
    return render(request, "core/inicio.html", {"saludo": saludo, **datos(request.user, filtro)})


def acceso_denegado(request, exception=None):
    return render(request, "403.html", status=403)


def no_encontrado(request, exception=None):
    return render(request, "404.html", status=404)


@login_required
@xframe_options_sameorigin
def archivo(request, ruta):
    """Los certificados y documentos solo se ven con la sesión iniciada (RNF-03)."""
    from pathlib import Path

    from django.conf import settings
    from django.http import FileResponse, Http404

    raiz = Path(settings.MEDIA_ROOT).resolve()
    destino = (raiz / ruta).resolve()
    if raiz not in destino.parents or not destino.is_file():
        raise Http404
    return FileResponse(open(destino, "rb"), filename=destino.name)
