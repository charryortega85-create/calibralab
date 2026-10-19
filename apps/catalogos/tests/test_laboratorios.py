"""Página de laboratorios y áreas, y el rol Encargado de laboratorio."""
import pytest
from django.urls import reverse

from apps.catalogos.models import Area, Laboratorio
from apps.cuentas.models import Rol
from conftest import _crear


@pytest.fixture
def labs(db):
    fq = Laboratorio.objects.create(nombre="Laboratorio Fisicoquímico")
    mb = Laboratorio.objects.create(nombre="Laboratorio Microbiológico")
    return {"fq": fq, "mb": mb, "quimica": Area.objects.create(laboratorio=fq, nombre="Química"),
            "micro": Area.objects.create(laboratorio=mb, nombre="Microbiología")}


@pytest.fixture
def encargado(labs):
    u = _crear("encargado", Rol.ENCARGADO)
    u.laboratorios.set([labs["fq"]])
    return u


def test_administrador_crea_laboratorio_y_area(cliente_de, admin):
    c = cliente_de(admin)
    assert c.post(reverse("catalogos:laboratorio_crear"), {"nombre": "Dirección de Zoonosis"}).status_code == 302
    lab = Laboratorio.objects.get(nombre="Dirección de Zoonosis")
    assert c.post(reverse("catalogos:area_crear"), {"laboratorio": lab.pk, "nombre": "EEB"}).status_code == 302
    html = c.get(reverse("catalogos:laboratorios")).content.decode()
    assert "Dirección de Zoonosis" in html and "EEB" in html


def test_encargado_ve_solo_su_laboratorio_sin_cambiarlo(cliente_de, encargado, labs):
    c = cliente_de(encargado)
    html = c.get(reverse("catalogos:laboratorios")).content.decode()
    assert "Laboratorio Fisicoquímico" in html and "Química" in html and "Laboratorio Microbiológico" not in html
    assert "Nuevo laboratorio" not in html and "Nueva área" not in html
    assert c.get(reverse("catalogos:laboratorio_crear")).status_code == 403
    assert c.get(reverse("catalogos:area_crear")).status_code == 403
    assert c.get(reverse("catalogos:area_editar", args=[labs["quimica"].pk])).status_code == 403
    r = c.post(reverse("catalogos:area_crear"), {"laboratorio": labs["fq"].pk, "nombre": "Física"})
    assert r.status_code == 403 and not Area.objects.filter(nombre="Física").exists()


def test_tecnico_y_consulta_no_entran(cliente_de, tecnico, consulta):
    for u in (tecnico, consulta):
        assert cliente_de(u).get(reverse("catalogos:laboratorios")).status_code == 403


def test_menu_del_encargado(cliente_de, encargado):
    html = cliente_de(encargado).get(reverse("core:inicio")).content.decode()
    assert f'href="{reverse("catalogos:laboratorios")}"' in html
    assert f'href="{reverse("cuentas:usuarios")}"' not in html
    assert f'href="{reverse("cuentas:configuracion")}"' not in html
    assert f'href="{reverse("catalogos:indice")}"' not in html


def test_encargado_sin_laboratorio_no_ve_equipos(cliente_de, labs, crear_equipo, admin):
    crear_equipo("EQ-0001", area=labs["quimica"], responsable=admin)
    nuevo = _crear("nuevo", Rol.ENCARGADO)
    assert "EQ-0001" not in cliente_de(nuevo).get(reverse("equipos:lista")).content.decode()


def test_solo_el_administrador_maneja_usuarios(cliente_de, encargado, tecnico):
    c = cliente_de(encargado)
    for url in (reverse("cuentas:usuarios"), reverse("cuentas:usuario_crear"),
                reverse("cuentas:usuario_editar", args=[tecnico.pk]),
                reverse("cuentas:usuario_contrasena", args=[tecnico.pk])):
        assert c.get(url).status_code == 403


def test_encargado_no_agrega_a_las_listas_al_cargar(cliente_de, encargado):
    html = cliente_de(encargado).get(reverse("equipos:importar")).content.decode()
    assert "crear_faltantes" not in html


def test_encargado_edita_equipos_de_su_laboratorio(cliente_de, encargado):
    assert cliente_de(encargado).get(reverse("equipos:crear")).status_code == 200
