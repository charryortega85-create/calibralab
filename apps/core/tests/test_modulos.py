"""RNF-03: cada rol ve y usa solo lo que le corresponde; las pantallas de todos los módulos responden."""
import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.alertas.estado import con_estado
from apps.equipos.models import Equipo
from apps.servicios.models import Servicio

LECTURA = ["equipos:lista", "servicios:lista", "alertas:estado", "alertas:avisos", "plan:indice", "plan:prioridad",
           "mantenimiento:indice", "reportes:indice", "reportes:estado", "reportes:vencimientos",
           "reportes:ejecucion"]
EDICION = ["equipos:crear", "equipos:importar", "servicios:crear", "plan:lote_crear", "plan:plan_crear"]
ADMIN = ["catalogos:indice", "auditoria:lista", "cuentas:usuarios"]


@pytest.mark.parametrize("nombre", LECTURA)
def test_todos_los_roles_consultan(cliente_de, consulta, nombre):
    assert cliente_de(consulta).get(reverse(nombre)).status_code == 200


@pytest.mark.parametrize("nombre", EDICION)
def test_consulta_no_edita(cliente_de, consulta, tecnico, nombre):
    assert cliente_de(consulta).get(reverse(nombre)).status_code == 403


@pytest.mark.parametrize("nombre", EDICION)
def test_tecnico_edita(cliente_de, tecnico, nombre):
    assert cliente_de(tecnico).get(reverse(nombre)).status_code == 200


@pytest.mark.parametrize("nombre", ADMIN)
def test_solo_administrador(cliente_de, tecnico, admin, nombre):
    assert cliente_de(tecnico).get(reverse(nombre)).status_code == 403
    assert cliente_de(admin).get(reverse(nombre)).status_code == 200


def test_sin_sesion_pide_ingresar(client):
    r = client.get(reverse("equipos:lista"))
    assert r.status_code == 302 and "/cuentas/" in r.url


def test_menu_enlaza_todos_los_modulos(cliente_de, admin):
    html = cliente_de(admin).get(reverse("core:inicio")).content.decode()
    assert "pronto" not in html
    for nombre in ("equipos:lista", "reportes:indice", "catalogos:indice"):
        assert f'href="{reverse(nombre)}"' in html


def test_menu_sin_plan_ni_mantenimiento(cliente_de, admin):
    html = cliente_de(admin).get(reverse("core:inicio")).content.decode()
    assert f'href="{reverse("plan:indice")}"' not in html
    assert f'href="{reverse("mantenimiento:indice")}"' not in html


def test_datos_de_ejemplo_y_pantallas_con_datos(cliente_de, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    call_command("cargar_demo", sin_archivos=True, stdout=open("/dev/null", "w"))
    call_command("cargar_demo", sin_archivos=True, stdout=open("/dev/null", "w"))  # no duplica
    assert Equipo.objects.count() == 36 and Servicio.objects.count() == 34
    from apps.cuentas.models import Usuario

    c = cliente_de(Usuario.objects.get(username="mperez"))
    e = Equipo.objects.get(codigo="EQ-0002")
    s = e.servicios.filter(resultado="no_conforme").get()
    assert e.estado == "fuera_servicio" and s.proxima_fecha is not None
    assert Servicio.objects.filter(resultado="").exists()
    assert Equipo.objects.filter(puntos__isnull=True).exists() and Equipo.objects.filter(puntos__isnull=False).exists()
    estados = set(con_estado().values_list("estado_cal", flat=True))
    assert {"vigente", "por_vencer", "vencido"} <= estados
    for url in [reverse("core:inicio"), e.get_absolute_url(), s.get_absolute_url(),
                reverse("reportes:hoja_vida", args=[e.pk]) + "?formato=html", reverse("alertas:avisos")]:
        assert c.get(url).status_code == 200, url
