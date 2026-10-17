"""
Qué equipos ve cada usuario según sus áreas. El Administrador y quien no tiene áreas
asignadas ven todos; el resto, los equipos de sus áreas, los que tiene a su cargo y lo
que cuelga de ellos (servicios, avisos, novedades…).
"""
from django.db.models import Q

from .models import Equipo


def _condicion(usuario, prefijo=""):
    return Q(**{f"{prefijo}area__in": usuario.areas.all()}) | Q(**{f"{prefijo}responsable": usuario})


def equipos_visibles(usuario, qs=None):
    qs = Equipo.objects.all() if qs is None else qs
    if usuario.ve_todas_las_areas:
        return qs
    return qs.filter(_condicion(usuario))


def del_usuario(usuario, qs, campo="equipo"):
    """Filtra servicios, avisos, novedades… por el equipo al que pertenecen."""
    if usuario.ve_todas_las_areas:
        return qs
    return qs.filter(_condicion(usuario, f"{campo}__"))
