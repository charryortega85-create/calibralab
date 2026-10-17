"""
Sugerencia del intervalo de calibración según el comportamiento del equipo.

Sigue la idea de ILAC-G24 / OIML D10: si el equipo usa poca tolerancia y no deriva, el intervalo
se puede alargar; si se acerca al límite o sale no apto, se acorta. Es solo una sugerencia:
el intervalo lo cambia una persona en la ficha del equipo.

«Uso de la tolerancia» de una calibración = el mayor |error| / EMP de sus puntos (|error| + U si
la calibración usó la regla con incertidumbre, igual que el dictamen). 100 %
significa que el punto peor llegó justo al límite. La deriva es la pendiente de ese uso en el
tiempo (recta de mínimos cuadrados sobre las últimas calibraciones aptas seguidas).
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

MINIMO, MAXIMO = 3, 36          # meses
LIMITE = Decimal("0.8")         # no dejar que el equipo llegue a más del 80 % de la tolerancia
HOLGADO = Decimal("0.5")        # por debajo del 50 % y sin deriva se puede alargar
ALARGAR, ACORTAR, REDUCIR = Decimal("1.5"), Decimal("0.75"), Decimal("0.5")
HISTORIAL = 5                   # calibraciones aptas que se miran como máximo

ACORTAR_TXT, ALARGAR_TXT, MANTENER, SIN_DATOS = "acortar", "alargar", "mantener", "sin_datos"


@dataclass
class Calibracion:
    fecha: date
    apta: bool
    uso: Decimal | None   # fracción de la tolerancia usada (0,35 = 35 %)


@dataclass
class Sugerencia:
    actual: int
    meses: int | None
    cambio: str
    motivo: str
    uso: Decimal | None = None
    deriva_anual: Decimal | None = None   # cuánto sube el uso en un año (0,10 = 10 puntos)

    @property
    def uso_pct(self):
        return None if self.uso is None else round(self.uso * 100)

    @property
    def deriva_pct(self):
        return None if self.deriva_anual is None else round(self.deriva_anual * 100, 1)


def _meses(a, b):
    return Decimal((b - a).days) / Decimal("30.4375")


def _pendiente(puntos):
    """Pendiente de mínimos cuadrados (uso por mes)."""
    n = len(puntos)
    mx = sum(x for x, _ in puntos) / n
    my = sum(y for _, y in puntos) / n
    den = sum((x - mx) ** 2 for x, _ in puntos)
    return Decimal(0) if den == 0 else sum((x - mx) * (y - my) for x, y in puntos) / den


def _acotar(meses, actual):
    bajo = min(actual, max(MINIMO, int(actual * REDUCIR)))
    alto = max(actual, min(MAXIMO, int(actual * ALARGAR)))
    return max(bajo, min(alto, int(meses)))


def sugerir(calibraciones, actual):
    """`calibraciones` en orden de fecha, de la más antigua a la más reciente."""
    if not calibraciones:
        return Sugerencia(actual, None, SIN_DATOS, "Todavía no tiene calibraciones.")
    ultima = calibraciones[-1]
    if not ultima.apta:
        meses = max(MINIMO, int(actual * REDUCIR))
        return Sugerencia(actual, meses, ACORTAR_TXT if meses < actual else MANTENER,
                          "La última calibración salió no apta: conviene acortar el intervalo a la mitad.", ultima.uso)
    seguidas = []
    for c in reversed(calibraciones):
        if not c.apta:
            break
        if c.uso is not None:
            seguidas.append(c)
    seguidas = list(reversed(seguidas[:HISTORIAL]))
    if not seguidas:
        return Sugerencia(actual, None, SIN_DATOS, "Las calibraciones no tienen errores registrados por punto.")
    uso = seguidas[-1].uso
    if uso > LIMITE:
        meses = max(MINIMO, int(actual * ACORTAR))
        return Sugerencia(actual, meses, ACORTAR_TXT if meses < actual else MANTENER,
                          f"En la última calibración usó el {round(uso * 100)} % de la tolerancia: "
                          "está cerca del límite.", uso)
    if len(seguidas) < 2:
        return Sugerencia(actual, actual, MANTENER,
                          "Hacen falta al menos dos calibraciones aptas seguidas para estimar la deriva.", uso)
    inicio = seguidas[0].fecha
    pendiente = _pendiente([(_meses(inicio, c.fecha), c.uso) for c in seguidas])
    deriva = pendiente * 12
    if pendiente > 0:
        hasta_limite = (LIMITE - uso) / pendiente
        meses = min(actual, _acotar(hasta_limite, actual))  # con deriva nunca se alarga
        motivo = (f"Usa el {round(uso * 100)} % de la tolerancia y sube unos {round(deriva * 100)} puntos por año: "
                  f"llegaría al 80 % en unos {int(hasta_limite)} meses.")
    elif uso < HOLGADO:
        meses = _acotar(actual * ALARGAR, actual)
        motivo = f"Usa solo el {round(uso * 100)} % de la tolerancia y no muestra deriva: el intervalo se puede alargar."
    else:
        meses = actual
        motivo = f"Usa el {round(uso * 100)} % de la tolerancia y no muestra deriva."
    cambio = ACORTAR_TXT if meses < actual else ALARGAR_TXT if meses > actual else MANTENER
    return Sugerencia(actual, meses, cambio, motivo, uso, deriva)


# --- Con los datos guardados ---------------------------------------------------------------------------

def uso_de_tolerancia(servicio):
    from .calculos import Regla

    con_u = servicio.regla == Regla.INCERTIDUMBRE
    usos = []
    for p in servicio.puntos.all():
        if p.error is None or not p.emp_aplicado:
            continue
        usos.append((abs(p.error) + (abs(p.incertidumbre or 0) if con_u else 0)) / p.emp_aplicado)
    return max(usos) if usos else None


def sugerencia_para(equipo):
    from .models import Resultado, TipoServicio

    servicios = (equipo.servicios.filter(tipo=TipoServicio.CALIBRACION).exclude(resultado="")
                 .order_by("fecha", "pk").prefetch_related("puntos"))
    historial = [Calibracion(s.fecha, s.resultado == Resultado.CONFORME, uso_de_tolerancia(s)) for s in servicios]
    return sugerir(historial, equipo.intervalo_meses)
