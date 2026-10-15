from django.urls import reverse


def test_inicio_muestra_nombre_y_rol(cliente_de, consulta):
    html = cliente_de(consulta).get(reverse("core:inicio")).content.decode()
    assert "Consulta" in html and "Panel de control" in html


def test_pagina_inexistente(cliente_de, tecnico, settings):
    settings.DEBUG = False
    assert cliente_de(tecnico).get("/no-existe/").status_code == 404
