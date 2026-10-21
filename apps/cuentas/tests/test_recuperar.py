"""RF-04: recuperar la contraseña con un enlace por correo."""
import re

import pytest
from django.core import mail
from django.core.cache import cache
from django.urls import reverse


@pytest.fixture(autouse=True)
def correo(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.URL_SISTEMA = "http://192.168.1.50:8000"
    cache.clear()


def _enlace():
    return re.search(r"http://192\.168\.1\.50:8000(/\S+)", mail.outbox[-1].body).group(1)


def test_la_persona_pide_el_enlace_y_cambia_su_contrasena(client, tecnico):
    r = client.post(reverse("cuentas:olvide"), {"dato": tecnico.username.upper()})
    assert r.status_code == 200 and "Revisa tu correo" in r.content.decode()
    assert mail.outbox[0].to == [tecnico.email]
    assert "- Su contraseña debe contener al menos 10 caracteres." in mail.outbox[0].body
    assert "- Su contraseña no puede ser completamente numérica." in mail.outbox[0].body
    r = client.get(_enlace(), follow=True)
    assert "Crea tu contraseña nueva" in r.content.decode()
    r = client.post(r.redirect_chain[-1][0], {"new_password1": "Otra-clave-2026", "new_password2": "Otra-clave-2026"},
                    follow=True)
    assert "Tu contraseña se cambió" in r.content.decode()
    tecnico.refresh_from_db()
    assert tecnico.check_password("Otra-clave-2026")


def test_el_enlace_sirve_una_sola_vez(client, tecnico):
    client.post(reverse("cuentas:olvide"), {"dato": tecnico.email})
    url = _enlace()
    r = client.get(url, follow=True)
    client.post(r.redirect_chain[-1][0], {"new_password1": "Otra-clave-2026", "new_password2": "Otra-clave-2026"})
    assert "El enlace ya no sirve" in client.get(url, follow=True).content.decode()


def test_no_revela_si_el_usuario_existe(client, tecnico):
    existe = client.post(reverse("cuentas:olvide"), {"dato": tecnico.username}).content.decode()
    no_existe = client.post(reverse("cuentas:olvide"), {"dato": "nadie"}).content.decode()
    assert "Revisa tu correo" in existe and "Revisa tu correo" in no_existe
    assert len(mail.outbox) == 1


def test_no_envia_dos_veces_seguidas_ni_a_desactivados(client, tecnico, consulta):
    client.post(reverse("cuentas:olvide"), {"dato": tecnico.username})
    client.post(reverse("cuentas:olvide"), {"dato": tecnico.username})
    consulta.is_active = False
    consulta.save()
    client.post(reverse("cuentas:olvide"), {"dato": consulta.username})
    assert len(mail.outbox) == 1


def test_administrador_envia_el_enlace(cliente_de, admin, tecnico):
    r = cliente_de(admin).post(reverse("cuentas:usuario_contrasena", args=[tecnico.pk]), {"enviar_enlace": "1"}, follow=True)
    assert f"Se envió a {tecnico.email}" in r.content.decode()
    assert "El administrador de CalibraLab" in mail.outbox[0].body and "/cuentas/nueva-contrasena/" in mail.outbox[0].body


def test_pantalla_de_ingreso_enlaza_la_recuperacion(client):
    assert reverse("cuentas:olvide") in client.get(reverse("cuentas:login")).content.decode()
