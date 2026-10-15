"""
Qué modelos se auditan y cómo.

Cada módulo registra sus modelos con `auditar(Modelo, ...)` en su `apps.py`. Así el
registro de cambios es automático (RF-39) y ningún módulo tiene que acordarse de escribirlo.
"""
from dataclasses import dataclass, field

from .middleware import ip_de, peticion_actual, usuario_actual
from .models import Accion, RegistroCambio


@dataclass
class ReglaAuditoria:
    excluir: set = field(default_factory=set)        # campos que no se registran
    ocultar: set = field(default_factory=set)        # se registra que cambió, sin mostrar el valor
    campos_estado: set = field(default_factory=set)  # sus cambios cuentan como «cambio de estado»
    equipo: callable = None                          # obtiene el código del equipo afectado


MODELOS_AUDITADOS = {}


def auditar(modelo, **opciones):
    MODELOS_AUDITADOS[modelo] = ReglaAuditoria(**opciones)


def texto(valor):
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    return str(valor)


def valores(instancia, regla):
    datos = {}
    for f in instancia._meta.concrete_fields:
        if f.primary_key or f.name in regla.excluir:
            continue
        if f.choices:
            datos[f.name] = texto(getattr(instancia, f"get_{f.name}_display")())
        elif f.is_relation:
            datos[f.name] = texto(getattr(instancia, f.name))
        else:
            datos[f.name] = texto(getattr(instancia, f.attname))
    return datos


def escribir(accion, *, instancia=None, regla=None, campo="", anterior="", nuevo="", usuario=None, objeto=""):
    peticion = peticion_actual()
    usuario = usuario or usuario_actual()
    fila = RegistroCambio(
        usuario=usuario,
        usuario_nombre=str(usuario) if usuario else "",
        accion=accion,
        campo=campo,
        valor_anterior=anterior,
        valor_nuevo=nuevo,
        ip=ip_de(peticion),
        objeto=objeto,
    )
    if instancia is not None:
        fila.modelo = str(instancia._meta.verbose_name)
        fila.objeto_id = str(instancia.pk)
        fila.objeto = str(instancia)[:255]
        if regla and regla.equipo:
            fila.equipo = texto(regla.equipo(instancia))
    fila.save()
    return fila


def etiqueta(instancia, nombre):
    return str(instancia._meta.get_field(nombre).verbose_name)


def registrar_guardado(instancia, anteriores, regla):
    if anteriores is None:
        escribir(Accion.ALTA, instancia=instancia, regla=regla)
        return
    actuales = valores(instancia, regla)
    for nombre, nuevo in actuales.items():
        anterior = anteriores.get(nombre, "")
        if anterior == nuevo:
            continue
        accion = Accion.CAMBIO_ESTADO if nombre in regla.campos_estado else Accion.MODIFICACION
        if nombre in regla.ocultar:
            anterior, nuevo = "(oculto)", "(cambiado)"
        escribir(accion, instancia=instancia, regla=regla, campo=etiqueta(instancia, nombre),
                 anterior=anterior, nuevo=nuevo)
