"""
Carga los datos inventados de la demostración: los 36 equipos de la maqueta del panel, con su
última calibración tal como la informa el proveedor (conforme, no conforme o sin dictamen) y los
puntos a calibrar en los equipos que los necesitan. Todos los datos son de ejemplo (II.1.7).
Se puede ejecutar más de una vez: no duplica nada.
"""
from datetime import date, datetime, time
from decimal import Decimal as D

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.alertas import avisos
from apps.alertas.models import Aviso, ResultadoEnvio, TipoAviso
from apps.catalogos.models import Area, Laboratorio, Marca, Proveedor, Ubicacion, Unidad
from apps.cuentas.models import Usuario
from apps.equipos.models import Criticidad, Equipo, EstadoEquipo, PuntoCalibracion, TipoEMP
from apps.servicios.models import PatronUtilizado, Resultado, Servicio, TipoServicio

RESPONSABLES = {"mp": "mperez", "lg": "lgimenez", "cb": "cbenitez", "ad": "aduarte"}

# Laboratorios y áreas inventados: cada ubicación de la maqueta cae en un área.
AREAS = {
    "Sala de balanzas": ("Laboratorio Fisicoquímico", "Metrología"),
    "Sala de metrología": ("Laboratorio Fisicoquímico", "Metrología"),
    "Sala de instrumentos": ("Laboratorio Fisicoquímico", "Metrología"),
    "Lab. de química": ("Laboratorio Fisicoquímico", "Química"),
    "Lab. de microbiología": ("Laboratorio Microbiológico", "Microbiología"),
    "Área de esterilización": ("Laboratorio Microbiológico", "Esterilización"),
}
# Dos técnicos trabajan solo en sus áreas, uno es encargado de un laboratorio entero y los demás ven todo.
AREAS_DE_USUARIOS = {"lgimenez": [("Laboratorio Fisicoquímico", "Química")],
                     "cbenitez": [("Laboratorio Microbiológico", "Microbiología"),
                                  ("Laboratorio Microbiológico", "Esterilización")]}


def area(laboratorio, nombre):
    lab = Laboratorio.objects.get_or_create(nombre=laboratorio)[0]
    return Area.objects.get_or_create(laboratorio=lab, nombre=nombre)[0]

# [código, equipo, marca, modelo, ubicación, criticidad, responsable, estado, intervalo, fecha, resultado,
#  tipo, proveedor, certificado, calibración anterior (si la última fue no conforme)], como en la maqueta
DATOS = [
    ["EQ-0001", "Balanza de precisión 1000 g", "Marca A", "B-1000", "Sala de balanzas", "Alta", "mp", "En servicio", 12, "2026-03-09", "Conforme", "Calibración", "Proveedor Y", "CC-2026-0187"],
    ["EQ-0002", "Termómetro digital", "Marca B", "T-200", "Lab. de química", "Media", "mp", "Fuera de servicio", 12, "2026-09-14", "No conforme", "Calibración", "Proveedor X", "CC-2026-0407", "2025-09-10"],
    ["EQ-0003", "Centrífuga de mesa", "Marca C", "CF-5", "Lab. de química", "Media", "mp", "En servicio", 12, "2025-10-30", "Conforme", "Calibración", "Proveedor X", "CC-2025-0508"],
    ["EQ-0004", "Balanza analítica 220 g", "Marca A", "BA-220", "Sala de balanzas", "Alta", "lg", "En servicio", 6, "2026-04-22", "Conforme", "Calibración", "Proveedor Y", "CC-2026-0231"],
    ["EQ-0005", "Espectrofotómetro UV-Vis", "Marca F", "UV-2100", "Sala de instrumentos", "Alta", "lg", "En servicio", 12, "2026-09-21", "Conforme", "Calibración", "Proveedor Y", "CC-2026-0428"],
    ["EQ-0006", "Incubadora 37 °C", "Marca E", "IN-60", "Lab. de microbiología", "Alta", "cb", "En servicio", 12, "2025-10-20", "Conforme", "Calificación", "Proveedor Z", "CQ-2025-0044"],
    ["EQ-0007", "Micropipeta 10–100 µL", "Marca D", "P-100", "Lab. de microbiología", "Media", "ad", "En servicio", 6, "2026-08-26", "Conforme", "Calibración", "Proveedor Z", "CC-2026-0377"],
    ["EQ-0008", "Estufa de secado", "Marca B", "E-80", "Sala de instrumentos", "Media", "mp", "En servicio", 12, "2026-09-28", "Conforme", "Calibración", "Proveedor X", "CC-2026-0436"],
    ["EQ-0009", "Manómetro 0–10 bar", "Marca G", "MN-10", "Sala de instrumentos", "Media", "ad", "En servicio", 12, "2025-11-11", "Conforme", "Calibración", "Proveedor X", "CC-2025-0531"],
    ["EQ-0010", "Campana de extracción de gases", "Marca H", "CE-120", "Lab. de química", "Alta", "lg", "En servicio", 12, "2026-02-17", "Conforme", "Certificación", "Proveedor Z", "CE-2026-0009"],
    ["EQ-0011", "Autoclave 50 L", "Marca E", "A-50", "Área de esterilización", "Alta", "cb", "En servicio", 12, "2026-10-09", "Conforme", "Calificación", "Proveedor Z", "CQ-2026-0052"],
    ["EQ-0012", "Refrigerador de laboratorio 2–8 °C", "Marca H", "RF-400", "Lab. de microbiología", "Alta", "lg", "En servicio", 12, "2025-09-30", "Conforme", "Calificación", "Proveedor Z", "CQ-2025-0041"],
    ["EQ-0013", "Pipeta automática 1–10 mL", "Marca D", "P-10M", "Lab. de química", "Media", "cb", "En servicio", 6, "2026-06-12", "Conforme", "Calibración", "Proveedor Z", "CC-2026-0322"],
    ["EQ-0014", "pH-metro de mesa", "Marca C", "PH-30", "Lab. de química", "Alta", "lg", "En servicio", 12, "2026-10-06", "Conforme", "Calibración", "Proveedor Y", "CC-2026-0441"],
    ["EQ-0015", "Conductímetro portátil", "Marca C", "CO-7", "Lab. de química", "Baja", "ad", "En servicio", 12, "2025-11-13", "Conforme", "Calibración", "Proveedor X", "CC-2025-0537"],
    ["EQ-0016", "Baño termostático", "Marca B", "BT-20", "Lab. de química", "Media", "cb", "En servicio", 12, "2025-11-04", "Conforme", "Calibración", "Proveedor X", "CC-2025-0520"],
    ["EQ-0017", "Juego de masas patrón F2", "Marca A", "MP-F2", "Sala de metrología", "Alta", "mp", "En servicio", 24, "2025-06-12", "Conforme", "Calibración", "Proveedor Y", "CC-2025-0302"],
    ["EQ-0018", "Cronómetro digital", "Marca A", "CR-1", "Sala de instrumentos", "Baja", "ad", "En servicio", 24, "2024-10-04", "Conforme", "Calibración", "Proveedor X", "CC-2024-0466"],
    ["EQ-0019", "Micropipeta 100–1000 µL", "Marca D", "P-1000", "Lab. de microbiología", "Media", "ad", "En servicio", 6, "2026-10-13", "Conforme", "Calibración", "Proveedor Z", "CC-2026-0452"],
    ["EQ-0020", "Turbidímetro", "Marca C", "TB-100", "Lab. de química", "Media", "cb", "En servicio", 12, "2025-08-19", "Conforme", "Calibración", "Proveedor Y", "CC-2025-0418"],
    ["EQ-0021", "Refractómetro digital", "Marca I", "RD-3", "Lab. de química", "Baja", "lg", "En servicio", 12, "2026-01-20", "Conforme", "Calibración", "Proveedor X", "CC-2026-0041"],
    ["EQ-0022", "Titulador automático", "Marca I", "TT-8", "Lab. de química", "Alta", "mp", "En servicio", 12, "2026-04-14", "Conforme", "Calibración", "Proveedor Y", "CC-2026-0224"],
    ["EQ-0023", "Mufla 1100 °C", "Marca B", "MF-11", "Sala de instrumentos", "Alta", "ad", "En reparación", 12, "2025-07-21", "Conforme", "Calibración", "Proveedor X", "CC-2025-0377"],
    ["EQ-0024", "Calibre pie de rey digital", "Marca J", "CP-150", "Sala de metrología", "Baja", "cb", "En servicio", 12, "2026-01-27", "Conforme", "Calibración", "Proveedor Y", "CC-2026-0049"],
    ["EQ-0025", "Micrómetro de exteriores", "Marca J", "MI-25", "Sala de metrología", "Baja", "cb", "En servicio", 12, "2026-02-03", "Conforme", "Calibración", "Proveedor Y", "CC-2026-0063"],
    ["EQ-0026", "Microscopio binocular", "Marca K", "MB-400", "Lab. de microbiología", "Media", "ad", "En servicio", 24, "2026-06-02", "Sin dictamen", "Calibración", "Proveedor Z", "CC-2026-0318"],
    ["EQ-0027", "Cabina de bioseguridad clase II", "Marca F", "CB-2", "Lab. de microbiología", "Alta", "ad", "En servicio", 12, "2026-10-02", "Conforme", "Certificación", "Proveedor Z", "CE-2026-0017"],
    ["EQ-0028", "Termohigrómetro de ambiente", "Marca A", "TH-10", "Sala de balanzas", "Baja", "mp", "En servicio", 12, "2026-09-17", "Conforme", "Calibración", "Proveedor X", "CC-2026-0419"],
    ["EQ-0029", "Cámara fría 2–8 °C", "Marca H", "CF-2", "Lab. de microbiología", "Alta", "cb", "En servicio", 12, "2026-08-12", "Conforme", "Calificación", "Proveedor Z", "CQ-2026-0038"],
    ["EQ-0030", "Fotómetro de llama", "Marca F", "FL-6", "Lab. de química", "Media", "lg", "En servicio", 12, "2026-07-22", "Conforme", "Calibración", "Proveedor Y", "CC-2026-0361"],
    ["EQ-0031", "Colorímetro portátil", "Marca I", "CL-2", "Lab. de química", "Baja", "mp", "En servicio", 12, "2026-03-24", "Conforme", "Calibración", "Proveedor X", "CC-2026-0203"],
    ["EQ-0032", "Medidor de oxígeno disuelto", "Marca C", "OD-5", "Lab. de química", "Media", "cb", "En servicio", 12, "2026-01-14", "Conforme", "Calibración", "Proveedor Y", "CC-2026-0033"],
    ["EQ-0033", "Densímetro digital", "Marca I", "DD-1", "Lab. de química", "Baja", "lg", "En servicio", 12, "2025-12-02", "Conforme", "Calibración", "Proveedor X", "CC-2025-0563"],
    ["EQ-0034", "Viscosímetro rotacional", "Marca I", "VR-2", "Lab. de química", "Media", "lg", "En servicio", 12, None],
    ["EQ-0035", "Agitador orbital", "Marca J", "AO-3", "Lab. de microbiología", "Baja", "ad", "En servicio", 12, None],
    ["EQ-0036", "Termómetro infrarrojo", "Marca A", "TI-5", "Sala de balanzas", "Baja", "mp", "En servicio", 12, None],
]

# (unidad, magnitud) y puntos [(nominal, tipo de EMP, EMP)] según el tipo de equipo; rango, resolución, capacidad
F, PL, PA = TipoEMP.FIJO, TipoEMP.PCT_LECTURA, TipoEMP.PCT_ALCANCE
PERFILES = [
    ("Balanza de precisión", "g", "masa", (0, 1000, "0.01", 1000), [(100, F, "0.5"), (500, F, "0.5"), (1000, F, "0.5")]),
    ("Balanza analítica", "g", "masa", (0, 220, "0.0001", 220), [(10, F, "0.0005"), (100, F, "0.001"), (200, F, "0.001")]),
    ("masas patrón", "g", "masa", (1, 1000, None, None), [(1, F, "0.0008"), (100, F, "0.005"), (1000, F, "0.05")]),
    ("Micropipeta 10–", "µL", "volumen", (10, 100, "0.1", 100), [(10, PL, "3"), (50, PL, "1.6"), (100, PL, "0.8")]),
    ("Micropipeta 100–", "µL", "volumen", (100, 1000, "1", 1000), [(100, PL, "3"), (500, PL, "1"), (1000, PL, "0.8")]),
    ("Pipeta automática", "mL", "volumen", (1, 10, "0.01", 10), [(1, PL, "3"), (5, PL, "1"), (10, PL, "0.6")]),
    ("Manómetro", "bar", "presión", (0, 10, "0.1", 10), [(2, PA, "1"), (5, PA, "1"), (8, PA, "1")]),
    ("pH-metro", "pH", "pH", (0, 14, "0.01", 14), [(4, F, "0.05"), (7, F, "0.05"), (10, F, "0.05")]),
    ("Centrífuga", "rpm", "velocidad de rotación", (500, 5000, "10", 5000), [(1000, PL, "2"), (3000, PL, "2")]),
    ("Cronómetro", "s", "tiempo", (0, 3600, "0.01", 3600), [(60, F, "0.1"), (600, F, "0.2")]),
    ("Calibre", "mm", "longitud", (0, 150, "0.01", 150), [(25, F, "0.03"), (100, F, "0.03")]),
    ("Micrómetro", "mm", "longitud", (0, 25, "0.001", 25), [(5, F, "0.004"), (20, F, "0.004")]),
    ("Espectrofotómetro", "nm", "longitud de onda", (190, 1100, "0.1", 1100), [(361, F, "1"), (536, F, "1")]),
    ("Conductímetro", "µS/cm", "conductividad", (0, 2000, "1", 2000), [(147, PL, "2"), (1413, PL, "2")]),
    ("Turbidímetro", "NTU", "turbidez", (0, 1000, "0.01", 1000), [(10, PL, "2"), (100, PL, "2")]),
    ("Termohigrómetro", "°C", "temperatura", (-10, 50, "0.1", None), [(20, F, "0.5"), (30, F, "0.5")]),
    ("Mufla", "°C", "temperatura", (100, 1100, "1", None), [(550, F, "10"), (900, F, "10")]),
    ("Refrigerador", "°C", "temperatura", (0, 15, "0.1", None), [(5, F, "1")]),
    ("Cámara fría", "°C", "temperatura", (0, 15, "0.1", None), [(5, F, "1")]),
    ("Incubadora", "°C", "temperatura", (20, 60, "0.1", None), [(37, F, "1")]),
    ("Autoclave", "°C", "temperatura", (100, 135, "0.1", None), [(121, F, "1")]),
    ("Estufa", "°C", "temperatura", (30, 250, "0.1", None), [(105, F, "2"), (180, F, "2")]),
    ("Baño", "°C", "temperatura", (20, 100, "0.1", None), [(37, F, "0.5"), (60, F, "0.5")]),
    ("Termómetro", "°C", "temperatura", (-50, 200, "0.1", None), [(0, F, "0.3"), (50, F, "0.3"), (100, F, "0.3")]),
    ("Campana", "m/s", "velocidad del aire", (0, 2, "0.01", None), [(0.5, F, "0.1")]),
    ("Cabina", "m/s", "velocidad del aire", (0, 2, "0.01", None), [(0.4, F, "0.05")]),
]
GENERICO = ("ud", "otra", (None, None, None, None), [(1, PL, "2")])
# Los puntos a calibrar son opcionales: el técnico los define solo en estos tipos de equipo.
CON_PUNTOS = ("Balanza", "masas patrón", "Micropipeta", "Pipeta", "Termómetro", "Termohigrómetro", "Manómetro",
              "pH-metro")
RESULTADOS = {"Conforme": Resultado.CONFORME, "No conforme": Resultado.NO_CONFORME, "Sin dictamen": ""}
# Errores del certificado de ejemplo en cada punto, como fracción del EMP (la demo es reproducible)
FRACCIONES = [D("0.4"), D("-0.6"), D("0.8")]


def perfil(descripcion):
    for clave, *resto in PERFILES:
        if clave.lower() in descripcion.lower():
            return resto
    return list(GENERICO)


def filas_de_ejemplo(s):
    """Valores por punto que muestra el PDF de ejemplo, inventados a partir de los puntos de la ficha."""
    filas = []
    for i, p in enumerate(s.equipo.puntos.filter(activo=True), start=1):
        emp = p.emp_valor if p.emp_tipo == TipoEMP.FIJO else (
            p.valor_nominal * p.emp_valor / 100 if p.emp_tipo == TipoEMP.PCT_LECTURA else s.equipo.capacidad * p.emp_valor / 100)
        fraccion = (D("1.6") if i == 1 else D("0.5")) if s.resultado == Resultado.NO_CONFORME else FRACCIONES[(i - 1) % 3]
        error = (emp * fraccion).quantize(D("0.000001"))
        filas.append({"referencia": p.valor_nominal, "leido": p.valor_nominal + error, "error": error,
                      "incertidumbre": (emp / 4).quantize(D("0.000001"))})
    return filas


def fecha(texto):
    return date.fromisoformat(texto) if texto else None


TECNICOS_PROVEEDOR = {"Proveedor X": ("Julio Benítez", "Sara Ojeda"), "Proveedor Y": ("Nora Cáceres", "Iván Rojas"),
                      "Proveedor Z": ("Pablo Ruiz", "Elena Vera")}
PATRONES = {
    "masa": [("PM-01", "Juego de pesas E2", "CP-2026-0101", "2027-05")],
    "volumen": [("PV-03", "Balanza analítica de referencia", "CP-2026-0144", "2027-02"),
                ("PT-07", "Termómetro de agua", "CP-2026-0150", "2027-03")],
    "temperatura": [("PT-15", "Termohigrómetro", "CP-2026-0122", "2027-04"),
                    ("PT-79", "Termómetro digital de referencia", "CP-2026-0188", "2027-08"),
                    ("PH-12", "Horno isotérmico", "CP-2025-0335", "2029-07")],
}


class Command(BaseCommand):
    help = "Carga los datos de ejemplo de la maqueta (equipos y calibraciones)."

    def add_arguments(self, parser):
        parser.add_argument("--sin-archivos", action="store_true",
                            help="No genera los PDF de ejemplo de los certificados (más rápido).")

    @transaction.atomic
    def handle(self, *args, sin_archivos=False, **opciones):
        call_command("crear_usuarios_demo", stdout=self.stdout)
        if Equipo.objects.filter(codigo="EQ-0001").exists():
            self.stdout.write("Los datos de ejemplo ya estaban cargados.")
            return
        self.usuarios = {k: Usuario.objects.get(username=v) for k, v in RESPONSABLES.items()}
        self.admin = self.usuarios["mp"]
        proveedores = {
            "Proveedor X": ("80012345-6", "Laboratorio acreditado ISO/IEC 17025 · temperatura, presión, química"),
            "Proveedor Y": ("80023456-7", "Laboratorio acreditado ISO/IEC 17025 · masa, volumen, longitud, óptica"),
            "Proveedor Z": ("80034567-8", "Laboratorio acreditado ISO/IEC 17025 · calificación térmica y bioseguridad"),
        }
        for nombre, (ruc, acred) in proveedores.items():
            Proveedor.objects.get_or_create(nombre=nombre, defaults={
                "ruc": ruc, "acreditacion": acred, "correo": f"{nombre[-1].lower()}@proveedor.example"})
        equipos = {fila[0]: self.equipo(fila) for fila in DATOS}
        for usuario, areas in AREAS_DE_USUARIOS.items():
            Usuario.objects.get(username=usuario).areas.set([area(*a) for a in areas])
        Usuario.objects.get(username="aduarte").laboratorios.set(
            [Laboratorio.objects.get(nombre="Laboratorio Fisicoquímico")])
        self.avisos()
        self.datos_certificados(generar_pdf=not sin_archivos)
        self.stdout.write(self.style.SUCCESS(f"Listo: {len(equipos)} equipos, {Servicio.objects.count()} calibraciones."))

    # ---------------------------------------------------------------------------------------------------
    def equipo(self, fila):
        codigo, desc, marca, modelo, ubic, crit, resp, estado, intervalo, f_ult = fila[:10]
        simbolo, magnitud, (rmin, rmax, res, cap), puntos = perfil(desc)
        unidad, _ = Unidad.objects.get_or_create(simbolo=simbolo, defaults={"nombre": f"{magnitud} ({simbolo})",
                                                                            "magnitud": magnitud})
        e = Equipo.objects.create(
            codigo=codigo, patrimonio=f"PAT-{codigo[-4:]}", descripcion=desc,
            marca=Marca.objects.get_or_create(nombre=marca)[0], modelo=modelo, numero_serie=f"SN{codigo[-4:]}-{modelo}",
            area=area(*AREAS[ubic]), ubicacion=Ubicacion.objects.get_or_create(nombre=ubic)[0], responsable=self.usuarios[resp], unidad=unidad,
            rango_min=rmin, rango_max=rmax, resolucion=D(res) if res else None, capacidad=cap,
            criticidad=Criticidad(crit.lower()), intervalo_meses=intervalo,
        )
        if not any(clave.lower() in desc.lower() for clave in CON_PUNTOS):
            puntos = []
        for i, (nominal, tipo, emp) in enumerate(puntos, start=1):
            PuntoCalibracion.objects.create(equipo=e, orden=i, valor_nominal=D(str(nominal)), emp_tipo=tipo, emp_valor=D(emp))
        if f_ult is None:
            return e
        resultado, tipo, proveedor, cert = fila[10:14]
        proveedor = Proveedor.objects.get(nombre=proveedor)
        if tipo != "Calibración":
            # Calificaciones y certificaciones quedan fuera del alcance: se registra la calibración del sensor.
            cert = cert.replace("CQ", "CC").replace("CE", "CC")
        if resultado == "No conforme":
            self.calibrar(e, fecha(fila[14]), proveedor, f"CC-{fila[14][:4]}-0{codigo[-3:]}", Resultado.CONFORME)
            s = self.calibrar(e, fecha(f_ult), proveedor, cert, Resultado.NO_CONFORME)
            # El sistema solo avisa; una persona decide sacar el equipo de servicio.
            e.cambiar_estado(EstadoEquipo.FUERA_DE_SERVICIO,
                             f"Certificado {cert} no conforme: la sonda quedó doblada",
                             self.admin, s.fecha)
        else:
            self.calibrar(e, fecha(f_ult), proveedor, cert, RESULTADOS[resultado])
        if estado == "En reparación":
            e.cambiar_estado(EstadoEquipo.EN_REPARACION, "Falla en la resistencia; enviado al servicio técnico",
                             self.usuarios[resp], date(2026, 10, 1))
        return e

    def calibrar(self, e, dia, proveedor, cert, resultado):
        s = Servicio(equipo=e, tipo=TipoServicio.CALIBRACION, fecha=dia, proveedor=proveedor, numero_certificado=cert,
                     resultado=resultado, trazabilidad="Patrones con trazabilidad al SI (INTN)",
                     registrado_por=e.responsable)
        s.calcular_proxima_fecha()
        s.save()
        return s

    def avisos(self):
        """Envía los avisos del día con un buzón de prueba y deja uno con error, como en la maqueta (RF-28)."""
        anterior = settings.EMAIL_BACKEND
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        try:
            enviados = avisos.enviar_pendientes()
        finally:
            settings.EMAIL_BACKEND = anterior
        ocho = timezone.make_aware(datetime.combine(timezone.localdate(), time(8, 0)))
        Aviso.objects.filter(pk__in=[a.pk for a in enviados]).update(enviado_en=ocho)
        Aviso.objects.filter(equipo__codigo="EQ-0012", tipo=TipoAviso.VENCIDO).update(
            resultado=ResultadoEnvio.ERROR, detalle="550 Buzón del destinatario lleno")

    def datos_certificados(self, generar_pdf):
        """Completa los datos del certificado y, si se pide, genera un PDF de ejemplo para el archivo."""
        if generar_pdf:
            try:
                import weasyprint  # noqa: F401
            except (OSError, ImportError):
                self.stdout.write(self.style.WARNING(
                    "No se generan los certificados de ejemplo en PDF: falta la biblioteca de PDF (GTK/Pango)."))
                generar_pdf = False
        from django.core.files.base import ContentFile
        from django.template.loader import render_to_string

        for s in Servicio.objects.select_related("equipo__unidad", "proveedor"):
            realizo, autorizo = TECNICOS_PROVEEDOR[s.proveedor.nombre]
            s.lugar = "En sitio, " + str(s.equipo.ubicacion) if s.equipo.criticidad == "alta" else f"Laboratorio de {s.proveedor}"
            s.temperatura_ambiente, s.humedad_relativa = D("20.4"), D("55")
            s.procedimiento = f"PRO-{s.equipo.unidad.magnitud[:3].upper()}-01 Rev.04"
            s.realizado_por, s.autorizado_por = realizo, autorizo
            s.trazabilidad = s.trazabilidad or "Patrones con trazabilidad al SI"
            s.save()
            for ident, desc, cert, prox in PATRONES.get(s.equipo.unidad.magnitud, PATRONES["temperatura"][:1]):
                PatronUtilizado.objects.create(servicio=s, identificacion=ident, descripcion=desc, certificado=cert,
                                               proxima_calibracion=prox)
            if generar_pdf:
                from weasyprint import HTML

                html = render_to_string("core/certificado_ejemplo.html", {"s": s, "filas": filas_de_ejemplo(s)})
                pdf = HTML(string=html).write_pdf()
                s.certificado.save(f"{s.numero_certificado}.pdf", ContentFile(pdf), save=True)
