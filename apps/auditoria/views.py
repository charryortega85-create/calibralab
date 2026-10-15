from datetime import datetime, time

from django.utils import timezone
from django.views.generic import ListView

from apps.cuentas.models import Usuario
from apps.cuentas.permisos import SoloAdministradorMixin

from .models import Accion, RegistroCambio


def _fecha(texto, fin=False):
    try:
        dia = datetime.strptime(texto, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return timezone.make_aware(datetime.combine(dia, time.max if fin else time.min))


class RegistroListaView(SoloAdministradorMixin, ListView):
    """RF-40: el administrador consulta y filtra el registro, sin poder modificarlo."""

    model = RegistroCambio
    template_name = "auditoria/registro_lista.html"
    context_object_name = "registros"
    paginate_by = 50

    def get_queryset(self):
        g = self.request.GET
        self.filtros = {k: g.get(k, "").strip() for k in ("usuario", "accion", "equipo", "desde", "hasta")}
        qs = RegistroCambio.objects.select_related("usuario")
        f = self.filtros
        if f["usuario"].isdigit():
            qs = qs.filter(usuario_id=int(f["usuario"]))
        if f["accion"] in Accion.values:
            qs = qs.filter(accion=f["accion"])
        if f["equipo"]:
            qs = qs.filter(equipo__icontains=f["equipo"])
        if desde := _fecha(f["desde"]):
            qs = qs.filter(fecha__gte=desde)
        if hasta := _fecha(f["hasta"], fin=True):
            qs = qs.filter(fecha__lte=hasta)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        consulta = self.request.GET.copy()
        consulta.pop("page", None)
        ctx.update(
            f=self.filtros,
            usuarios=Usuario.objects.order_by("nombre"),
            acciones=Accion.choices,
            consulta=consulta.urlencode(),
        )
        return ctx
