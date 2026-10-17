"""
RF-12: carga de varios equipos a la vez desde Excel o CSV.

Primero se revisan todas las filas con las mismas reglas del formulario de alta y se
muestran los errores; solo si no hay ninguno se guardan todas juntas (RNF-10).
"""
import csv
import io
from dataclasses import dataclass, field

from openpyxl import load_workbook

from apps.catalogos.models import Area, Marca, Ubicacion, Unidad
from apps.cuentas.models import Usuario

from .forms import EquipoForm
from .models import Criticidad

# (encabezado en el archivo, campo del formulario, descripción para la plantilla)
COLUMNAS = [
    ("codigo", "codigo", "Código interno único, por ejemplo EQ-0001"),
    ("patrimonio", "patrimonio", "N.º de patrimonio (opcional)"),
    ("descripcion", "descripcion", "Descripción del equipo"),
    ("marca", "marca", "Nombre de la marca, tal como figura en la lista de marcas"),
    ("modelo", "modelo", "Modelo"),
    ("numero_serie", "numero_serie", "N.º de serie"),
    ("laboratorio", "laboratorio", "Nombre del laboratorio, tal como figura en la lista"),
    ("area", "area", "Nombre del área dentro de ese laboratorio"),
    ("ubicacion", "ubicacion", "Nombre de la ubicación, tal como figura en la lista"),
    ("responsable", "responsable", "Usuario del responsable, por ejemplo mperez"),
    ("unidad", "unidad", "Símbolo de la unidad de medida, por ejemplo g o °C"),
    ("rango_min", "rango_min", "Rango desde (opcional)"),
    ("rango_max", "rango_max", "Rango hasta (opcional)"),
    ("resolucion", "resolucion", "Resolución (opcional)"),
    ("capacidad", "capacidad", "Capacidad o alcance (opcional)"),
    ("tolerancia", "tolerancia", "Tolerancia (opcional)"),
    ("criticidad", "criticidad", "Alta, Media o Baja"),
    ("intervalo_meses", "intervalo_meses", "Intervalo de calibración en meses"),
]
ENCABEZADOS = [c[0] for c in COLUMNAS]


@dataclass
class Fila:
    numero: int
    datos: dict
    errores: list = field(default_factory=list)

    @property
    def codigo(self):
        return self.datos.get("codigo", "")


def leer(archivo):
    """Devuelve una lista de diccionarios con los encabezados en minúsculas."""
    nombre = archivo.name.lower()
    if nombre.endswith(".xlsx"):
        wb = load_workbook(archivo, read_only=True, data_only=True)
        filas = list(wb.active.iter_rows(values_only=True))
    else:
        texto = archivo.read().decode("utf-8-sig", errors="replace")
        dialecto = csv.Sniffer().sniff(texto[:2048], delimiters=";,\t") if texto.strip() else csv.excel
        filas = list(csv.reader(io.StringIO(texto), dialecto))
    if not filas:
        return []
    enc = [str(c or "").strip().lower() for c in filas[0]]
    salida = []
    for valores in filas[1:]:
        if not any(v not in (None, "") for v in valores):
            continue
        salida.append({enc[i]: ("" if v is None else str(v).strip()) for i, v in enumerate(valores) if i < len(enc)})
    return salida


def _buscar(modelo, campo, valor, etiqueta, errores):
    if not valor:
        return ""
    obj = modelo.objects.filter(**{f"{campo}__iexact": valor}).first()
    if obj is None:
        errores.append(f"{etiqueta} «{valor}» no existe en la lista. Pide al administrador que la agregue.")
        return ""
    return obj.pk


def _buscar_area(laboratorio, area, usuario, errores):
    """El área por su nombre (y el del laboratorio). Si se deja vacía y el usuario tiene una sola área, va a esa."""
    if not area:
        if usuario is not None and not usuario.ve_todas_las_areas and usuario.areas_permitidas().count() == 1:
            return usuario.areas_permitidas().get().pk
        return ""
    qs = Area.objects.filter(nombre__iexact=area)
    if laboratorio:
        qs = qs.filter(laboratorio__nombre__iexact=laboratorio)
    encontradas = list(qs[:2])
    if not encontradas:
        donde = f" del laboratorio «{laboratorio}»" if laboratorio else ""
        errores.append(f"El área «{area}»{donde} no existe en la lista. Pide al administrador que la agregue.")
        return ""
    if len(encontradas) > 1:
        errores.append(f"Hay varias áreas «{area}»: escribe también el laboratorio.")
        return ""
    return encontradas[0].pk


def validar(registros, usuario=None):
    faltan = [c for c in ("codigo", "descripcion", "marca", "modelo", "numero_serie") if registros and c not in registros[0]]
    if faltan:
        return [Fila(1, {}, [f"Faltan columnas en el archivo: {', '.join(faltan)}. Usa la plantilla."])]
    filas, vistos_codigo, vistos_serie = [], {}, {}
    criticidades = {e.lower(): v for v, e in Criticidad.choices}
    for n, reg in enumerate(registros, start=2):
        fila = Fila(n, {c: reg.get(c, "") for c in ENCABEZADOS})
        e = fila.errores
        d = dict(fila.datos)
        d["marca"] = _buscar(Marca, "nombre", d["marca"], "La marca", e)
        d["area"] = _buscar_area(d.pop("laboratorio"), d["area"], usuario, e)
        d["ubicacion"] = _buscar(Ubicacion, "nombre", d["ubicacion"], "La ubicación", e)
        d["unidad"] = _buscar(Unidad, "simbolo", d["unidad"], "La unidad", e)
        d["responsable"] = _buscar(Usuario, "username", d["responsable"], "El usuario responsable", e)
        d["criticidad"] = criticidades.get((d["criticidad"] or "media").lower(), d["criticidad"])
        for num in ("rango_min", "rango_max", "resolucion", "capacidad"):
            d[num] = d[num].replace(",", ".")
        d["intervalo_meses"] = d["intervalo_meses"] or "12"
        form = EquipoForm(data=d, usuario=usuario)
        if not form.is_valid():
            for campo, errs in form.errors.items():
                etiqueta = form.fields[campo].label if campo in form.fields else ""
                e.extend(f"{etiqueta}: {x}" if etiqueta else x for x in errs)
        codigo = d["codigo"].strip().upper()
        if codigo in vistos_codigo:
            e.append(f"El código {codigo} se repite en la fila {vistos_codigo[codigo]} del archivo.")
        vistos_codigo.setdefault(codigo, n)
        clave = (d["marca"], d["modelo"].strip().lower(), d["numero_serie"].strip().lower())
        if all(clave) and clave in vistos_serie:
            e.append(f"Marca, modelo y n.º de serie se repiten en la fila {vistos_serie[clave]} del archivo.")
        vistos_serie.setdefault(clave, n)
        fila.datos = d
        filas.append(fila)
    return filas


def guardar(filas, usuario=None):
    creados = []
    for f in filas:
        form = EquipoForm(data=f.datos, usuario=usuario)
        if not form.is_valid():  # Algo cambió desde la revisión: se cancela todo.
            raise ValueError(f"La fila {f.numero} dejó de ser válida: {form.errors.as_text()}")
        equipo = form.save(commit=False)
        equipo._change_reason = "Carga masiva desde archivo"
        equipo.save()
        creados.append(equipo)
    return creados
