"""Datos del panel de inicio (RF-26), con el mismo contenido que la maqueta aprobada."""
import math
from datetime import date, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.alertas.estado import activos, conteo, prioridades
from apps.alertas.models import Aviso, ResultadoEnvio
from apps.cuentas.models import Configuracion, Rol, Usuario
from apps.equipos.acceso import del_usuario, equipos_visibles
from apps.equipos.models import Equipo, EstadoEquipo
from apps.servicios.calculos import Estado, sumar_meses
from apps.servicios.models import Resultado, Servicio

COLORES = {Estado.VIGENTE: "#22c55e", Estado.POR_VENCER: "#f59e0b", Estado.VENCIDO: "#ef4444",
           Estado.SIN_REGISTRO: "#94a3b8"}
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def dona(cnt, total):
    r, c = 48, 2 * math.pi * 48
    segmentos, acum = [], 0.0
    for k in Estado.ORDEN:
        n = cnt[k]
        if not n:
            continue
        largo = n / total * c
        segmentos.append({"color": COLORES[k], "visible": round(max(largo - 2.2, 1), 2),
                          "resto": round(c, 2), "offset": round(-acum, 2)})
        acum += largo
    return segmentos


def datos(usuario, filtro_servicios="todos"):
    hoy = timezone.localdate()
    ahora = timezone.localtime()
    conf = Configuracion.actual()
    equipos = equipos_visibles(usuario)  # solo los de sus áreas, si las tiene
    cnt = conteo(equipos, dia=hoy)
    total = sum(cnt.values())
    por_estado = dict(equipos.values_list("estado").annotate(n=Count("id")))

    proximas = [p for p in prioridades(equipos, dia=hoy) if p.equipo.estado_cal == Estado.POR_VENCER]
    proxima = min(proximas, key=lambda p: p.dias) if proximas else None

    hace30 = ahora - timedelta(days=30)
    recientes = del_usuario(usuario, Aviso.objects.filter(enviado_en__gte=hace30))
    errores = recientes.filter(resultado=ResultadoEnvio.ERROR).count()

    # Alertas por técnico (un técnico ve solo su fila; Administrador y Consulta ven todas)
    responsables = Usuario.objects.filter(is_active=True, equipos__in=equipos).distinct()
    if usuario.rol == Rol.TECNICO:
        responsables = responsables.filter(pk=usuario.pk)
    tecnicos = []
    for t in responsables:
        c = conteo(equipos.filter(responsable=t), dia=hoy)
        tecnicos.append({"u": t, "vencidos": c[Estado.VENCIDO], "por_vencer": c[Estado.POR_VENCER],
                         "ultimo": del_usuario(usuario, Aviso.objects.filter(destinatario=t)).select_related("equipo").first(),
                         "avisos": del_usuario(usuario, Aviso.objects.filter(destinatario=t)).select_related("equipo")[:4]})

    servicios = del_usuario(usuario, Servicio.objects.select_related("equipo", "proveedor"))
    if filtro_servicios == "conformes":
        servicios = servicios.filter(resultado=Resultado.CONFORME)
    elif filtro_servicios == "no_conformes":
        servicios = servicios.filter(resultado=Resultado.NO_CONFORME)
    ultimos = list(servicios[:8])
    estados_eq = {e.pk: e for e in activos(Equipo.objects.filter(pk__in=[s.equipo_id for s in ultimos]), dia=hoy)}
    for s in ultimos:
        s.eq_estado = estados_eq.get(s.equipo_id)
        s.dias_desde = (s.fecha - hoy).days

    # Vencimientos de los próximos 6 meses
    con_fecha = activos(equipos, dia=hoy).filter(proxima__isnull=False, proxima__gte=hoy).values_list("proxima", flat=True)
    columnas = [{"etiqueta": "Vencidos", "n": cnt[Estado.VENCIDO], "mal": True}]
    inicio_mes = date(hoy.year, hoy.month, 1)
    fechas = list(con_fecha)
    for i in range(6):
        m = sumar_meses(inicio_mes, i)
        n = sum(1 for f in fechas if f.year == m.year and f.month == m.month)
        columnas.append({"etiqueta": MESES_CORTOS[m.month - 1], "n": n, "mal": False,
                         "titulo": f"{n} equipo{'s' if n != 1 else ''} vence{'n' if n != 1 else ''} en {m:%m/%Y}"})
    maximo = max([1] + [c["n"] for c in columnas])
    for c in columnas:
        c["alto"] = round(c["n"] * 100 / maximo)
    dentro = sum(c["n"] for c in columnas[1:])

    siguiente = timezone.make_aware(timezone.datetime.combine(hoy, conf.hora_envio))
    if siguiente <= ahora:
        siguiente += timedelta(days=1)

    return {
        "hoy": hoy, "cnt": cnt, "total": total, "plazo": conf.plazo_aviso_dias, "conf": conf,
        "en_servicio": por_estado.get(EstadoEquipo.EN_SERVICIO, 0),
        "en_reparacion": por_estado.get(EstadoEquipo.EN_REPARACION, 0),
        "fuera_servicio": por_estado.get(EstadoEquipo.FUERA_DE_SERVICIO, 0),
        "de_baja": por_estado.get(EstadoEquipo.BAJA, 0),
        "pct_vencidos": round(cnt[Estado.VENCIDO] * 100 / total, 1) if total else 0,
        "proxima": proxima, "avisos_30": recientes.count(), "avisos_err": errores,
        "avisos_ok": recientes.count() - errores, "tecnicos": tecnicos,
        "segmentos": dona(cnt, total) if total else [],
        "leyenda": [{"k": k, "txt": Estado.ETIQUETAS[k], "n": cnt[k], "color": COLORES[k],
                     "pct": round(cnt[k] * 100 / total, 1) if total else 0} for k in Estado.ORDEN],
        "validos": cnt[Estado.VIGENTE] + cnt[Estado.POR_VENCER],
        "pct_validos": round((cnt[Estado.VIGENTE] + cnt[Estado.POR_VENCER]) * 100 / total, 1) if total else 0,
        "ultimos": ultimos, "filtro": filtro_servicios, "prioridad": prioridades(equipos, dia=hoy, limite=7),
        "n_prioridad": cnt[Estado.VENCIDO] + cnt[Estado.POR_VENCER],
        "barras": columnas, "dentro_6": dentro, "mas_adelante": len(fechas) - dentro, "siguiente_envio": siguiente,
    }
