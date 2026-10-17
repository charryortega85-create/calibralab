"""Laboratorios y áreas: cada usuario ve y registra solo los equipos de sus áreas."""
from datetime import date

import pytest
from django.urls import reverse

from apps.catalogos.models import Area, Laboratorio
from apps.cuentas.models import Rol
from apps.equipos.models import Equipo
from conftest import _crear

from .test_equipos import datos_equipo


@pytest.fixture
def areas(db):
    fq = Laboratorio.objects.create(nombre="Laboratorio Fisicoquímico")
    mb = Laboratorio.objects.create(nombre="Laboratorio Microbiológico")
    return {"quimica": Area.objects.create(laboratorio=fq, nombre="Química"),
            "metrologia": Area.objects.create(laboratorio=fq, nombre="Metrología"),
            "micro": Area.objects.create(laboratorio=mb, nombre="Microbiología")}


@pytest.fixture
def escenario(areas, crear_equipo, calibrar, admin):
    """Un equipo en Química y otro en Microbiología, de un responsable que no es la técnica de Química."""
    q = crear_equipo("EQ-0001", area=areas["quimica"], responsable=admin)
    m = crear_equipo("EQ-0002", area=areas["micro"], responsable=admin)
    calibrar(q, date(2025, 1, 10), numero="CC-Q")
    calibrar(m, date(2025, 1, 10), numero="CC-M")
    quimica = _crear("quimica", Rol.TECNICO)
    quimica.areas.set([areas["quimica"]])
    return {"q": q, "m": m, "usuario": quimica}


def test_ve_solo_los_equipos_de_su_area(cliente_de, escenario):
    c = cliente_de(escenario["usuario"])
    html = c.get(reverse("equipos:lista")).content.decode()
    assert "EQ-0001" in html and "EQ-0002" not in html
    assert c.get(reverse("equipos:ficha", args=[escenario["m"].pk])).status_code == 404
    assert c.get(reverse("equipos:ficha", args=[escenario["q"].pk])).status_code == 200


@pytest.mark.parametrize("pantalla", ["servicios:lista", "servicios:certificados", "alertas:estado",
                                      "core:inicio", "reportes:estado"])
def test_otras_pantallas_tambien_filtran(cliente_de, escenario, pantalla):
    html = cliente_de(escenario["usuario"]).get(reverse(pantalla)).content.decode()
    assert "EQ-0002" not in html and "CC-M" not in html


def test_servicio_de_otra_area_no_se_abre(cliente_de, escenario):
    s = escenario["m"].servicios.get()
    c = cliente_de(escenario["usuario"])
    assert c.get(reverse("servicios:detalle", args=[s.pk])).status_code == 404
    assert c.get(reverse("servicios:crear") + f"?equipo={escenario['m'].pk}").status_code == 404


def test_administrador_y_usuario_sin_areas_ven_todo(cliente_de, escenario, admin, tecnico):
    for u in (admin, tecnico):
        html = cliente_de(u).get(reverse("equipos:lista")).content.decode()
        assert "EQ-0001" in html and "EQ-0002" in html


def test_ve_los_equipos_que_tiene_a_su_cargo_aunque_sean_de_otra_area(cliente_de, escenario):
    m = escenario["m"]
    m.responsable = escenario["usuario"]
    m.save()
    assert cliente_de(escenario["usuario"]).get(reverse("equipos:ficha", args=[m.pk])).status_code == 200


def test_filtro_por_laboratorio_y_area(cliente_de, escenario, admin, areas):
    c = cliente_de(admin)
    html = c.get(reverse("equipos:lista"), {"area": areas["micro"].laboratorio.filtro}).content.decode()
    assert "EQ-0002" in html and "EQ-0001" not in html
    html = c.get(reverse("equipos:lista"), {"area": areas["quimica"].pk}).content.decode()
    assert "EQ-0001" in html and "EQ-0002" not in html


def test_alta_solo_en_sus_areas_y_area_obligatoria(cliente_de, escenario, catalogo, areas):
    u = escenario["usuario"]
    c = cliente_de(u)
    r = c.post(reverse("equipos:crear"), datos_equipo(catalogo, u, area=areas["micro"].pk))
    assert r.status_code == 200 and not Equipo.objects.filter(codigo="EQ-0100").exists()
    r = c.post(reverse("equipos:crear"), datos_equipo(catalogo, u))
    assert r.status_code == 200 and not Equipo.objects.filter(codigo="EQ-0100").exists()
    r = c.post(reverse("equipos:crear"), datos_equipo(catalogo, u, area=areas["quimica"].pk))
    assert r.status_code == 302 and Equipo.objects.get(codigo="EQ-0100").area == areas["quimica"]


def test_administrador_asigna_areas_al_usuario(cliente_de, admin, tecnico, areas):
    datos = {"nombre": tecnico.nombre, "email": tecnico.email, "rol": tecnico.rol, "is_active": "on",
             "areas": [areas["quimica"].pk, areas["metrologia"].pk]}
    r = cliente_de(admin).post(reverse("cuentas:usuario_editar", args=[tecnico.pk]), datos)
    assert r.status_code == 302
    assert set(tecnico.areas.all()) == {areas["quimica"], areas["metrologia"]}
    html = cliente_de(admin).get(reverse("cuentas:usuarios")).content.decode()
    assert "Laboratorio Fisicoquímico · Química" in html


def test_formulario_de_usuario_muestra_las_areas(cliente_de, admin, areas):
    html = cliente_de(admin).get(reverse("cuentas:usuario_crear")).content.decode()
    assert 'type="checkbox" name="areas"' in html and "Microbiología" in html


def test_consulta_ve_todas_las_areas_aunque_tenga_areas_marcadas(cliente_de, escenario, consulta, areas):
    consulta.areas.set([areas["quimica"]])
    html = cliente_de(consulta).get(reverse("equipos:lista")).content.decode()
    assert "EQ-0001" in html and "EQ-0002" in html
