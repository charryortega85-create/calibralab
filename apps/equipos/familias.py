"""
Datos técnicos propios de cada familia de instrumentos.

Se guardan en Equipo.caracteristicas (JSON) para no llenar la tabla de columnas que solo usa una
familia. La misma definición arma el formulario, la ficha y las hojas del Excel de carga.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class Dato:
    clave: str         # también es la columna del Excel
    etiqueta: str
    tipo: str = "texto"  # texto, numero, entero u opciones
    opciones: tuple = ()
    ayuda: str = ""


FAMILIAS = {
    "balanza": [
        Dato("clase_exactitud", "Clase de exactitud", "opciones", ("I", "II", "III", "IIII"),
             "Según OIML R76: I especial, II fina, III media."),
        Dato("division_d", "División de escala (d)", "numero", ayuda="En la unidad del equipo."),
        Dato("division_e", "División de verificación (e)", "numero", ayuda="En la unidad del equipo."),
    ],
    "termico": [
        Dato("setpoints", "Temperaturas de uso", ayuda="Separadas por punto y coma, por ejemplo 37; 121."),
        Dato("sensores_mapeo", "Sensores del mapeo", "entero", ayuda="Por ejemplo 9 o 15."),
        Dato("volumen_camara_l", "Volumen de la cámara (L)", "numero"),
    ],
    "cabina": [
        Dato("clase_cabina", "Clase de cabina", "opciones", ("I", "II A1", "II A2", "II B1", "II B2", "III")),
        Dato("tamano", "Tamaño", ayuda="Por ejemplo 4 pies o 1,2 m."),
    ],
    "lector": [
        Dato("longitudes_onda", "Longitudes de onda (nm)", ayuda="Separadas por punto y coma, por ejemplo 405; 450; 492; 620."),
        Dato("pocillos", "Placa", "opciones", ("96", "384")),
    ],
    "pipeta": [
        Dato("canales", "Canales", "opciones", ("1", "8", "12", "16")),
        Dato("volumen_nominal_ul", "Volumen nominal (µL)", "numero", ayuda="El mayor volumen que mide."),
        Dato("tipo_volumen", "Volumen", "opciones", ("Fijo", "Variable")),
    ],
    "otro": [],
}


def datos(familia):
    return FAMILIAS.get(familia or "otro", [])


def limpiar(dato, valor):
    """Normaliza un valor escrito por una persona. Devuelve (valor, error)."""
    valor = "" if valor is None else str(valor).strip()
    if valor == "":
        return "", None
    if dato.tipo in ("numero", "entero"):
        try:
            n = Decimal(valor.replace(",", "."))
        except InvalidOperation:
            return "", f"{dato.etiqueta}: escribe un número."
        if n < 0:
            return "", f"{dato.etiqueta}: no puede ser negativo."
        if dato.tipo == "entero":
            if n != n.to_integral_value():
                return "", f"{dato.etiqueta}: escribe un número entero."
            return str(int(n)), None
        return f"{n.normalize():f}", None
    if dato.tipo == "opciones":
        for o in dato.opciones:
            if o.lower() == valor.lower():
                return o, None
        return "", f"{dato.etiqueta}: elige {', '.join(dato.opciones)}."
    return valor, None


def mostrar(familia, valores):
    valores = valores or {}
    return [(d.etiqueta, valores[d.clave]) for d in datos(familia) if valores.get(d.clave) not in (None, "")]
