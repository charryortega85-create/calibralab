"""Página de laboratorios y áreas, y el rol Encargado de laboratorio."""
import pytest
from django.urls import reverse

from apps.catalogos.models import Area, Laboratorio
from apps.cuentas.models import Rol, Usuario
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


def test_encargado_ve_solo_su_laboratorio_y_agrega_areas(cliente_de, encargado, labs):
    c = cliente_de(encargado)
    html = c.get(reverse("catalogos:laboratorios")).content.decode()
    assert "Laboratorio Fisicoquímico" in html and "Laboratorio Microbiológico" not in html
    assert "Nuevo laboratorio" not in html
    assert c.get(reverse("catalogos:laboratorio_crear")).status_code == 403
    # Solo puede elegir sus laboratorios
    r = c.post(reverse("catalogos:area_crear"), {"laboratorio": labs["mb"].pk, "nombre": "Otra"})
    assert r.status_code == 200 and not Area.objects.filter(nombre="Otra").exists()
    assert c.post(reverse("catalogos:area_crear"), {"laboratorio": labs["fq"].pk, "nombre": "Física"}).status_code == 302
    assert Area.objects.filter(laboratorio=labs["fq"], nombre="Física").exists()
    assert c.get(reverse("catalogos:area_editar", args=[labs["micro"].pk])).status_code == 404
    assert c.get(reverse("catalogos:area_editar", args=[labs["quimica"].pk])).status_code == 200


def test_tecnico_y_consulta_no_entran(cliente_de, tecnico, consulta):
    for u in (tecnico, consulta):
        assert cliente_de(u).get(reverse("catalogos:laboratorios")).status_code == 403


def test_menu_del_encargado(cliente_de, encargado):
    html = cliente_de(encargado).get(reverse("core:inicio")).content.decode()
    assert f'href="{reverse("catalogos:laboratorios")}"' in html and f'href="{reverse("cuentas:usuarios")}"' in html
    assert f'href="{reverse("cuentas:configuracion")}"' not in html
    assert f'href="{reverse("catalogos:indice")}"' not in html


def test_encargado_sin_laboratorio_no_ve_equipos(cliente_de, labs, crear_equipo, admin):
    crear_equipo("EQ-0001", area=labs["quimica"], responsable=admin)
    nuevo = _crear("nuevo", Rol.ENCARGADO)
    assert "EQ-0001" not in cliente_de(nuevo).get(reverse("equipos:lista")).content.decode()


def test_encargado_gestiona_solo_los_tecnicos_de_su_laboratorio(cliente_de, encargado, labs, admin):
    suyo = _crear("suyo", Rol.TECNICO)
    suyo.areas.set([labs["quimica"]])
    ajeno = _crear("ajeno", Rol.TECNICO)
    ajeno.areas.set([labs["micro"]])
    c = cliente_de(encargado)
    html = c.get(reverse("cuentas:usuarios")).content.decode()
    assert "suyo" in html and "ajeno" not in html and ">admin<" not in html
    assert c.get(reverse("cuentas:usuario_editar", args=[ajeno.pk])).status_code == 404
    assert c.get(reverse("cuentas:usuario_editar", args=[admin.pk])).status_code == 404
    assert c.get(reverse("cuentas:usuario_contrasena", args=[ajeno.pk])).status_code == 404


def test_encargado_crea_tecnicos_solo_con_sus_areas(cliente_de, encargado, labs):
    c = cliente_de(encargado)
    base = {"nombre": "Nueva Técnica", "username": "nueva", "email": "nueva@lab.example",
            "password1": "Clave-segura-2026", "password2": "Clave-segura-2026"}
    # No puede crear administradores ni dejarla sin área (vería todo)
    r = c.post(reverse("cuentas:usuario_crear"), {**base, "rol": Rol.ADMINISTRADOR, "areas": [labs["quimica"].pk]})
    assert r.status_code == 200 and not Usuario.objects.filter(username="nueva").exists()
    r = c.post(reverse("cuentas:usuario_crear"), {**base, "rol": Rol.TECNICO})
    assert r.status_code == 200 and not Usuario.objects.filter(username="nueva").exists()
    r = c.post(reverse("cuentas:usuario_crear"), {**base, "rol": Rol.TECNICO, "areas": [labs["micro"].pk]})
    assert r.status_code == 200 and not Usuario.objects.filter(username="nueva").exists()
    r = c.post(reverse("cuentas:usuario_crear"), {**base, "rol": Rol.TECNICO, "areas": [labs["quimica"].pk]})
    assert r.status_code == 302
    nueva = Usuario.objects.get(username="nueva")
    assert nueva.rol == Rol.TECNICO and list(nueva.areas.all()) == [labs["quimica"]]


def test_encargado_conserva_las_areas_de_otros_laboratorios(cliente_de, encargado, labs):
    t = _crear("mixto", Rol.TECNICO)
    t.areas.set([labs["quimica"], labs["micro"]])
    fisica = Area.objects.create(laboratorio=labs["fq"], nombre="Física")
    datos = {"nombre": t.nombre, "email": t.email, "rol": Rol.TECNICO, "is_active": "on", "areas": [fisica.pk]}
    assert cliente_de(encargado).post(reverse("cuentas:usuario_editar", args=[t.pk]), datos).status_code == 302
    assert set(t.areas.all()) == {fisica, labs["micro"]}


def test_encargado_edita_equipos_de_su_laboratorio(cliente_de, encargado):
    assert cliente_de(encargado).get(reverse("equipos:crear")).status_code == 200
