"""Menú lateral: cada rol ve solo las opciones que le corresponden (RF-02)."""
from django.urls import NoReverseMatch, reverse

# (grupo, texto, icono, nombre de URL o None si el módulo aún no está construido, módulo, solo administrador)
MENU = [
    ("Principal", "Inicio", "i-home", "core:inicio", "", False),
    ("Principal", "Equipos", "i-flask", "equipos:lista", "B", False),
    ("Principal", "Calibraciones", "i-gauge", "servicios:lista", "C", False),
    ("Principal", "Certificados", "i-file", "servicios:certificados", "C", False),
    ("Principal", "Estado y alertas", "i-bell", "alertas:estado", "D", False),
    ("Gestión", "Plan y presupuesto", "i-calendar", "plan:indice", "E", False),
    ("Gestión", "Mantenimiento", "i-wrench", "mantenimiento:indice", "F", False),
    ("Gestión", "Reportes", "i-chart", "reportes:indice", "G", False),
    ("Sistema", "Registro de cambios", "i-history", "auditoria:lista", "H", True),
    ("Sistema", "Listas controladas", "i-box", "catalogos:indice", "B", True),
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
        grupos.setdefault(grupo, []).append(
            {"texto": texto, "icono": icono, "url": url, "modulo": modulo, "activo": False}
        )
    # Se marca solo la opción cuya dirección coincide más larga (Certificados dentro de /servicios/).
    coinciden = [it for items in grupos.values() for it in items
                 if it["url"] and (ruta == it["url"] if it["url"] == "/" else ruta.startswith(it["url"]))]
    if coinciden:
        max(coinciden, key=lambda it: len(it["url"]))["activo"] = True
    return {"menu_grupos": grupos.items()}
