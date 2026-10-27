"""Etiquetas de estado: siempre texto + icono + color, nunca solo color (RNF-19)."""
from decimal import Decimal

from django import template
from django.utils.html import format_html, format_html_join

register = template.Library()

ESTADOS_CAL = {
    "vigente": ("b-ok", "i-check", "Vigente"),
    "por_vencer": ("b-warn", "i-clock", "Por vencer"),
    "vencido": ("b-bad", "i-alert", "Vencido"),
    "sin_registro": ("b-mute", "i-minus", "Sin registro"),
}


def _badge(clase, icono, texto, titulo=""):
    return format_html('<span class="badge {}"{}><svg class="i" aria-hidden="true"><use href="#{}"/></svg>{}</span>',
                       clase, format_html(' title="{}"', titulo) if titulo else "", icono, texto)


@register.filter
def estado_cal(valor):
    clase, icono, texto = ESTADOS_CAL.get(valor, ESTADOS_CAL["sin_registro"])
    return _badge(clase, icono, texto)


@register.filter
def marca_no_conforme(resultado):
    """Marca junto al estado cuando la última calibración se informó no conforme."""
    if resultado != "no_conforme":
        return ""
    return _badge("b-bad", "i-x", "No conforme", "La última calibración se informó no conforme")


@register.filter
def dictamen(servicio):
    if not servicio or not servicio.resultado:
        return _badge("b-mute", "i-minus", "Sin dictamen")
    ok = servicio.conforme
    return _badge("b-ok" if ok else "b-bad", "i-check" if ok else "i-x", servicio.dictamen)


@register.filter
def cumple(valor):
    if valor is None:
        return "—"
    return _badge("b-ok", "i-check", "Cumple") if valor else _badge("b-bad", "i-x", "No cumple")


@register.filter
def estado_equipo(equipo):
    clases = {"en_servicio": "b-ok", "en_reparacion": "b-warn", "fuera_servicio": "b-bad", "baja": "b-mute"}
    return format_html('<span class="tag {}">{}</span>', clases.get(equipo.estado, ""), equipo.get_estado_display())


@register.filter
def criticidad(valor):
    n = {"alta": 3, "media": 2, "baja": 1}.get(valor, 0)
    barras = format_html_join("", '<i class="{}"></i>', (("on" if i <= n else "",) for i in (1, 2, 3)))
    return format_html('<span class="crit" title="Criticidad {}"><span class="lv" aria-hidden="true">{}</span>{}</span>',
                       valor, barras, str(valor).capitalize())


@register.filter
def relativo(dias):
    if dias is None:
        return ""
    if dias == 0:
        return "hoy"
    if dias == 1:
        return "mañana"
    if dias == -1:
        return "ayer"
    return f"en {dias} días" if dias > 0 else f"hace {-dias} días"


@register.filter
def num(valor):
    """Muestra un decimal sin ceros sobrantes: 0.500000 → 0,5."""
    if valor is None or valor == "":
        return "—"
    if isinstance(valor, Decimal):
        texto = f"{valor.normalize():f}"
        return texto.replace(".", ",")
    return valor


@register.filter
def guaranies(valor):
    if valor is None:
        return "—"
    return f"₲ {int(valor):,}".replace(",", ".")


@register.simple_tag
def icono(nombre):
    return format_html('<svg class="i" aria-hidden="true"><use href="#{}"/></svg>', nombre)
