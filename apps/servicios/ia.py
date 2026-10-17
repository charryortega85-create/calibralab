"""
Lectura de certificados con IA (opcional).

Se envía el PDF o la foto del certificado al servicio de IA de Anthropic, que devuelve los
datos en un formato fijo. El sistema los ubica en el formulario de registro del servicio y
una persona los revisa antes de guardar: la IA nunca guarda nada por su cuenta (RN-08).
Cada lectura queda registrada con su costo (LecturaIA).
"""
import base64
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.utils import timezone

from apps.catalogos.models import Proveedor

from .models import LecturaIA, TipoServicio

TIPOS_IMAGEN = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
CAMPOS_TEXTO = ["numero_certificado", "lugar", "procedimiento", "realizado_por", "autorizado_por", "trazabilidad"]
CAMPOS_NUMERO = ["temperatura_ambiente", "humedad_relativa"]
# Modelos que aceptan reintentar en otro modelo si el primero declina la solicitud.
CON_REINTENTO = ("claude-opus", "claude-sonnet", "claude-fable")

_texto = {"type": "string"}
ESQUEMA = {
    "type": "object",
    "properties": {
        "tipo": {"type": "string", "enum": ["calibracion", "calificacion", "certificacion"]},
        "fecha": _texto, "numero_certificado": _texto, "proveedor": _texto, "lugar": _texto,
        "temperatura_ambiente": _texto, "humedad_relativa": _texto, "procedimiento": _texto,
        "realizado_por": _texto, "autorizado_por": _texto, "trazabilidad": _texto,
        "puntos": {"type": "array", "items": {
            "type": "object",
            "properties": {"valor_referencia": _texto, "valor_leido": _texto, "error_informado": _texto,
                           "incertidumbre": _texto},
            "required": ["valor_referencia", "valor_leido", "error_informado", "incertidumbre"],
            "additionalProperties": False,
        }},
        "patrones": {"type": "array", "items": {
            "type": "object",
            "properties": {"identificacion": _texto, "descripcion": _texto, "certificado": _texto,
                           "proxima_calibracion": _texto},
            "required": ["identificacion", "descripcion", "certificado", "proxima_calibracion"],
            "additionalProperties": False,
        }},
        "notas": _texto,
    },
    "required": ["tipo", "fecha", "numero_certificado", "proveedor", "lugar", "temperatura_ambiente",
                 "humedad_relativa", "procedimiento", "realizado_por", "autorizado_por", "trazabilidad",
                 "puntos", "patrones", "notas"],
    "additionalProperties": False,
}

INSTRUCCIONES = """Lee este certificado de un servicio a un equipo de laboratorio y devuelve sus datos.

Equipo: {equipo}
Unidad de medida del equipo: {unidad}
Puntos de calibración de la ficha del equipo: {puntos}

Reglas:
- Copia solo lo que está escrito en el certificado. Si un dato no figura, deja el texto vacío. No inventes ni completes valores.
- tipo: «calibracion», «calificacion» o «certificacion», según el servicio que describe el certificado.
- fecha: la fecha de ejecución del servicio (no la de emisión), en formato AAAA-MM-DD.
- proveedor: el nombre del laboratorio que emitió el certificado.
- Números: con punto decimal y sin separador de miles (por ejemplo 1000.25). Temperatura en °C y humedad en %.
- puntos: una fila por punto medido, con los valores convertidos a la unidad del equipo ({unidad}).
  valor_referencia es el valor del patrón; valor_leido, lo que indicó el equipo; error_informado, el error que informa
  el certificado (si informa una «corrección», el error es la corrección con el signo cambiado); incertidumbre, la
  incertidumbre expandida U. Si están el valor leído y el error, completa los dos.
- patrones: los patrones o instrumentos de referencia usados, con su certificado y su próxima calibración (AAAA-MM).
- notas: en una o dos frases, lo que no se pudo leer bien o lo que conviene revisar. Vacío si todo está claro."""


class ErrorLectura(Exception):
    pass


def disponible():
    return bool(settings.IA_CLAVE)


def contar_hojas(datos, extension):
    if extension != "pdf":
        return 1
    return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", datos)) or 1


def _cliente():
    import anthropic

    return anthropic.Anthropic(api_key=settings.IA_CLAVE, timeout=180.0, max_retries=2)


def _bloque(datos, extension):
    b64 = base64.standard_b64encode(datos).decode("ascii")
    if extension == "pdf":
        return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}}
    return {"type": "image", "source": {"type": "base64", "media_type": TIPOS_IMAGEN[extension], "data": b64}}


def _costo(respuesta, modelo):
    """Suma cada intento (si el primer modelo declinó y respondió otro, se cobran los dos)."""
    usos = getattr(respuesta.usage, "iterations", None) or [respuesta.usage]
    entrada = salida = 0
    costo = Decimal("0")
    for u in usos:
        e = (u.input_tokens or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0) + \
            (getattr(u, "cache_read_input_tokens", 0) or 0)
        s = u.output_tokens or 0
        entrada, salida = entrada + e, salida + s
        precio = settings.IA_PRECIOS.get(getattr(u, "model", None) or modelo)
        if precio is None:
            costo = None
        elif costo is not None:
            costo += (Decimal(e) * Decimal(str(precio[0])) + Decimal(s) * Decimal(str(precio[1]))) / 1_000_000
    return entrada, salida, (costo.quantize(Decimal("0.0001")) if costo is not None else None)


def _preguntar(datos, extension, equipo, puntos_ficha):
    modelo = settings.IA_MODELO
    texto = INSTRUCCIONES.format(
        equipo=f"{equipo.codigo} · {equipo.descripcion} · {equipo.marca} {equipo.modelo}",
        unidad=equipo.unidad.simbolo,
        puntos=", ".join(f"{p.valor_nominal.normalize():f}" for p in puntos_ficha) or "sin puntos definidos",
    )
    extra = {}
    if modelo.startswith(CON_REINTENTO):
        extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    return _cliente().beta.messages.create(
        model=modelo, max_tokens=16000,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA}},
        messages=[{"role": "user", "content": [_bloque(datos, extension), {"type": "text", "text": texto}]}],
        **extra,
    )


def leer_certificado(archivo, equipo, puntos_ficha, usuario):
    """Devuelve los valores para el formulario y deja registrada la lectura con su costo."""
    if not disponible():
        raise ErrorLectura("La lectura con IA no está activada. El administrador debe configurar ANTHROPIC_API_KEY.")
    extension = archivo.name.rsplit(".", 1)[-1].lower() if "." in archivo.name else ""
    if extension != "pdf" and extension not in TIPOS_IMAGEN:
        raise ErrorLectura("La IA lee certificados en PDF o en foto (JPG, PNG o WEBP).")
    if archivo.size > settings.TAMANO_MAXIMO_ADJUNTO_MB * 1024 * 1024:
        raise ErrorLectura(f"El archivo pesa más de {settings.TAMANO_MAXIMO_ADJUNTO_MB} MB.")
    datos = archivo.read()
    archivo.seek(0)
    hojas = contar_hojas(datos, extension)
    if hojas > settings.IA_MAXIMO_HOJAS:
        raise ErrorLectura(f"El certificado tiene {hojas} hojas y el máximo para leer con IA es "
                           f"{settings.IA_MAXIMO_HOJAS}. Carga los datos a mano.")

    registro = LecturaIA(usuario=usuario, equipo=equipo, archivo=archivo.name[:200], hojas=hojas,
                         modelo=settings.IA_MODELO)
    try:
        respuesta = _preguntar(datos, extension, equipo, puntos_ficha)
    except Exception as e:  # sin conexión, clave inválida, límite de uso…
        registro.mensaje = f"Error del servicio de IA: {type(e).__name__}"[:300]
        registro.save()
        raise ErrorLectura("No se pudo conectar con el servicio de IA. Revisa la conexión a internet y la clave, "
                           "o carga los datos a mano.") from e
    registro.modelo = getattr(respuesta, "model", None) or settings.IA_MODELO
    registro.tokens_entrada, registro.tokens_salida, registro.costo_usd = _costo(respuesta, settings.IA_MODELO)
    if respuesta.stop_reason != "end_turn":
        registro.mensaje = f"Respuesta incompleta ({respuesta.stop_reason})"
        registro.save()
        raise ErrorLectura("La IA no pudo leer este certificado. Carga los datos a mano.")
    try:
        texto = next(b.text for b in respuesta.content if b.type == "text")
        leido = json.loads(texto)
    except (StopIteration, ValueError) as e:
        registro.mensaje = "La respuesta no tenía el formato esperado"
        registro.save()
        raise ErrorLectura("La IA devolvió una respuesta que no se pudo usar. Carga los datos a mano.") from e
    registro.exito = True
    registro.save()
    resultado = a_formulario(leido, puntos_ficha)
    resultado.update({"hojas": hojas, "costo_usd": str(registro.costo_usd) if registro.costo_usd is not None else None})
    return resultado


# --- De la respuesta de la IA a los campos del formulario ----------------------------------------------

def _numero(texto):
    texto = (texto or "").strip().replace(",", ".").replace(" ", "")
    if not texto:
        return None
    try:
        return Decimal(texto)
    except InvalidOperation:
        return None


def _proveedor(nombre, avisos):
    nombre = (nombre or "").strip()
    if not nombre:
        return None
    activos = Proveedor.objects.filter(activo=True)
    p = activos.filter(nombre__iexact=nombre).first()
    if p is None:
        p = next((x for x in activos if x.nombre.lower() in nombre.lower() or nombre.lower() in x.nombre.lower()), None)
    if p is None:
        avisos.append(f"El proveedor «{nombre}» no está en la lista de proveedores. Elígelo o pide que lo agreguen.")
    return p


def a_formulario(leido, puntos_ficha):
    """Ubica cada dato en su campo. Lo dudoso no se completa: se avisa para que la persona lo revise."""
    campos, avisos = {}, []
    if leido.get("tipo") in TipoServicio.values:
        campos["tipo"] = leido["tipo"]
    try:
        fecha = date.fromisoformat((leido.get("fecha") or "").strip())
        if fecha <= timezone.localdate():
            campos["fecha"] = fecha.isoformat()
        else:
            avisos.append(f"La fecha leída ({fecha}) es futura; revísala.")
    except ValueError:
        if leido.get("fecha"):
            avisos.append(f"No se entendió la fecha «{leido['fecha']}».")
    for c in CAMPOS_TEXTO:
        if (leido.get(c) or "").strip():
            campos[c] = leido[c].strip()
    for c in CAMPOS_NUMERO:
        n = _numero(leido.get(c))
        if n is not None:
            campos[c] = f"{n.normalize():f}"
    proveedor = _proveedor(leido.get("proveedor"), avisos)
    if proveedor:
        campos["proveedor"] = str(proveedor.pk)

    puntos, usados = [], set()
    for p in leido.get("puntos") or []:
        ref = _numero(p.get("valor_referencia"))
        if ref is None:
            continue
        fila = _fila_cercana(ref, puntos_ficha, usados)
        if fila is None:
            avisos.append(f"El punto {ref.normalize():f} del certificado no está en la ficha del equipo; no se cargó.")
            continue
        usados.add(fila)
        leido_v, error, u = _numero(p.get("valor_leido")), _numero(p.get("error_informado")), _numero(p.get("incertidumbre"))
        datos = {"valor_referencia": f"{ref.normalize():f}"}
        if leido_v is not None:
            datos["valor_leido"] = f"{leido_v.normalize():f}"  # con el valor leído el sistema calcula el error
        elif error is not None:
            datos["error_informado"] = f"{error.normalize():f}"
        if u is not None:
            datos["incertidumbre"] = f"{abs(u).normalize():f}"
        puntos.append({"fila": fila, **datos})
    faltan = len(puntos_ficha) - len(usados)
    if puntos_ficha and faltan:
        avisos.append(f"{faltan} punto{'s' if faltan != 1 else ''} de la ficha no aparece{'n' if faltan != 1 else ''} "
                      "en el certificado.")

    patrones = [{k: (v or "").strip() for k, v in pat.items()} for pat in (leido.get("patrones") or [])
                if (pat.get("identificacion") or "").strip()]
    for pat in patrones:
        if not re.fullmatch(r"\d{4}-\d{2}", pat.get("proxima_calibracion", "")):
            pat["proxima_calibracion"] = ""
    if (leido.get("notas") or "").strip():
        avisos.append(f"Nota de la lectura: {leido['notas'].strip()}")
    return {"campos": campos, "puntos": puntos, "patrones": patrones, "avisos": avisos}


def _fila_cercana(ref, puntos_ficha, usados):
    """El punto de la ficha con el mismo valor nominal (tolerancia del 2 %)."""
    mejor, distancia = None, None
    for i, p in enumerate(puntos_ficha):
        if i in usados:
            continue
        d = abs(p.valor_nominal - ref)
        limite = max(abs(p.valor_nominal) * Decimal("0.02"), Decimal("0.000001"))
        if d <= limite and (distancia is None or d < distancia):
            mejor, distancia = i, d
    return mejor
