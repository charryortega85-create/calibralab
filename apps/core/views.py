from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone


@login_required
def inicio(request):
    """
    Pantalla de inicio (RF-26). Por ahora da la bienvenida; los indicadores de la
    maqueta se completan cuando existan los módulos B, C y D.
    """
    ahora = timezone.localtime()
    saludo = "Buenos días" if ahora.hour < 12 else "Buenas tardes" if ahora.hour < 19 else "Buenas noches"
    return render(request, "core/inicio.html", {"saludo": saludo, "hoy": ahora})


def acceso_denegado(request, exception=None):
    return render(request, "403.html", status=403)


def no_encontrado(request, exception=None):
    return render(request, "404.html", status=404)
