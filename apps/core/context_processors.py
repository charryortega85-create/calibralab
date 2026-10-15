"""Menú lateral: cada rol ve solo las opciones que le corresponden (RF-02)."""
from django.urls import NoReverseMatch, reverse

# (grupo, texto, icono, nombre de URL o None si el módulo aún no está construido, módulo, solo administrador)
MENU = [
    ("Principal", "Inicio", "i-home", "core:inicio", "", False),
    ("Principal", "Equipos", "i-flask", None, "B", False),
    ("Principal", "Calibraciones", "i-gauge", None, "C", False),
    ("Principal", "Estado y alertas", "i-bell", None, "D", False),
    ("Gestión", "Plan y presupuesto", "i-calendar", None, "E", False),
    ("Gestión", "Mantenimiento", "i-wrench", None, "F", False),
    ("Gestión", "Reportes", "i-chart", None, "G", False),
    ("Sistema", "Registro de cambios", "i-history", "auditoria:lista", "H", True),
    ("Sistema", "Usuarios", "i-users", "cuentas:usuarios", "A", True),
    ("Sistema", "Configuración", "i-settings", "cuentas:configuracion", "A", True),
]


def menu(request):
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return {}
    ruta = request.path
    grupos = {}
    for grupo, texto, icono, nombre_url, modulo, solo_admin in MENU:
        if solo_admin and not usuario.es_administrador:
            continue
        try:
            url = reverse(nombre_url) if nombre_url else None
        except NoReverseMatch:
            url = None
        activo = bool(url) and (ruta == url if url == "/" else ruta.startswith(url))
        grupos.setdefault(grupo, []).append(
            {"texto": texto, "icono": icono, "url": url, "modulo": modulo, "activo": activo}
        )
    return {"menu_grupos": grupos.items()}
