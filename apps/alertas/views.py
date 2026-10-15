from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.cuentas.models import Usuario
from apps.cuentas.permisos import SOLO_ADMIN, rol_requerido

from . import avisos as av
from .estado import conteo, prioridades
from .models import Aviso, ResultadoEnvio, TipoAviso


@login_required
def estado(request):
    """CU-15: equipos vencidos y por vencer, ordenados por urgencia y criticidad (RF-26, RF-33)."""
    return render(request, "alertas/estado.html", {
        "lista": prioridades(), "cnt": conteo(),
    })


@login_required
def avisos(request):
    """CU-16: historial de avisos enviados, con su resultado."""
    g = request.GET
    f = {k: g.get(k, "") for k in ("tipo", "resultado", "destinatario")}
    qs = Aviso.objects.select_related("equipo", "destinatario")
    if f["tipo"] in TipoAviso.values:
        qs = qs.filter(tipo=f["tipo"])
    if f["resultado"] in ResultadoEnvio.values:
        qs = qs.filter(resultado=f["resultado"])
    if f["destinatario"].isdigit():
        qs = qs.filter(destinatario_id=f["destinatario"])
    pagina = Paginator(qs, 30).get_page(g.get("page"))
    consulta = g.copy()
    consulta.pop("page", None)
    return render(request, "alertas/avisos.html", {
        "pagina": pagina, "f": f, "consulta": consulta.urlencode(), "tipos": TipoAviso.choices,
        "resultados": ResultadoEnvio.choices, "usuarios": Usuario.objects.exclude(rol="consulta"),
        "pendientes": av.pendientes(),
    })


@rol_requerido(*SOLO_ADMIN)
def enviar_ahora(request):
    """Envía ya los avisos pendientes (los que fallaron se reintentan). Útil en la demostración."""
    if request.method == "POST":
        enviados = av.enviar_pendientes()
        errores = sum(1 for a in enviados if a.resultado == ResultadoEnvio.ERROR)
        messages.success(request, f"Avisos enviados: {len(enviados) - errores}. Con error: {errores}.")
    return redirect("alertas:avisos")


@login_required
def aviso(request, pk):
    return render(request, "alertas/aviso.html", {"a": get_object_or_404(Aviso.objects.select_related("equipo"), pk=pk)})
