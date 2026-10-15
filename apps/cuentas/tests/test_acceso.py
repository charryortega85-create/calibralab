"""Pruebas del módulo A: acceso y usuarios (RF-01 a RF-04, RNF-01 a RNF-05)."""
import pytest
from django.conf import settings
from django.urls import reverse

from apps.cuentas.models import Configuracion, Rol, Usuario
from conftest import CLAVE

LOGIN = reverse("cuentas:login")


def ingresar(client, usuario, clave=CLAVE):
    return client.post(LOGIN, {"username": usuario, "password": clave})


class TestIngreso:
    def test_sin_sesion_redirige_al_ingreso(self, client, db):
        r = client.get(reverse("core:inicio"))
        assert r.status_code == 302 and r.url.startswith(LOGIN)

    def test_ingresa_con_datos_correctos(self, client, tecnico):
        r = ingresar(client, "tecnico")
        assert r.status_code == 302 and r.url == reverse("core:inicio")
        assert client.get(reverse("core:inicio")).status_code == 200

    @pytest.mark.parametrize("usuario,clave", [("", ""), ("tecnico", "clave-equivocada"), ("nadie", CLAVE)])
    def test_rechaza_datos_vacios_o_falsos(self, client, tecnico, usuario, clave):
        r = ingresar(client, usuario, clave)
        assert r.status_code == 200
        assert "_auth_user_id" not in client.session

    def test_usuario_desactivado_no_ingresa(self, client, tecnico):
        tecnico.is_active = False
        tecnico.save()
        ingresar(client, "tecnico")
        assert "_auth_user_id" not in client.session

    def test_cerrar_sesion(self, client, tecnico):
        ingresar(client, "tecnico")
        client.post(reverse("cuentas:logout"))
        assert "_auth_user_id" not in client.session

    def test_bloqueo_tras_5_intentos_fallidos(self, client, tecnico):
        """RNF-05: tras 5 fallos seguidos, ni la clave correcta entra."""
        for _ in range(5):
            ingresar(client, "tecnico", "clave-equivocada")
        r = ingresar(client, "tecnico")
        assert r.status_code == 429
        assert "_auth_user_id" not in client.session

    def test_sesion_expira_a_los_20_minutos(self):
        assert settings.SESSION_COOKIE_AGE == 20 * 60
        assert settings.SESSION_SAVE_EVERY_REQUEST


class TestContrasenas:
    def test_contrasena_guardada_con_hash(self, tecnico):
        """RNF-02: en la base de datos no hay contraseñas legibles."""
        assert CLAVE not in tecnico.password
        assert tecnico.password.startswith(("pbkdf2_", "argon2", "scrypt"))

    def test_rechaza_contrasena_corta(self, cliente_de, admin):
        c = cliente_de(admin)
        datos = {"nombre": "Nueva", "username": "nueva", "email": "n@lab.example", "rol": Rol.TECNICO,
                 "password1": "Corta-1", "password2": "Corta-1"}
        r = c.post(reverse("cuentas:usuario_crear"), datos)
        assert r.status_code == 200
        assert not Usuario.objects.filter(username="nueva").exists()

    def test_cada_usuario_cambia_su_contrasena(self, client, tecnico):
        """RF-04."""
        ingresar(client, "tecnico")
        nueva = "Otra-clave-segura-456"
        r = client.post(reverse("cuentas:cambiar_contrasena"),
                        {"old_password": CLAVE, "new_password1": nueva, "new_password2": nueva})
        assert r.status_code == 302
        tecnico.refresh_from_db()
        assert tecnico.check_password(nueva)


class TestPermisosPorRol:
    """RF-02 y RNF-03: cada rol ve solo lo suyo, aunque escriba la dirección a mano."""

    PANTALLAS_ADMIN = ["cuentas:usuarios", "cuentas:usuario_crear", "cuentas:configuracion", "auditoria:lista"]

    @pytest.mark.parametrize("pantalla", PANTALLAS_ADMIN)
    @pytest.mark.parametrize("rol", ["tecnico", "consulta"])
    def test_pantallas_de_administrador_negadas(self, request, cliente_de, pantalla, rol):
        c = cliente_de(request.getfixturevalue(rol))
        assert c.get(reverse(pantalla)).status_code == 403

    @pytest.mark.parametrize("pantalla", PANTALLAS_ADMIN)
    def test_administrador_las_ve(self, cliente_de, admin, pantalla):
        assert cliente_de(admin).get(reverse(pantalla)).status_code == 200

    def test_menu_oculta_opciones_de_administrador(self, cliente_de, tecnico):
        html = cliente_de(tecnico).get(reverse("core:inicio")).content.decode()
        assert reverse("cuentas:usuarios") not in html
        assert reverse("auditoria:lista") not in html

    def test_menu_del_administrador(self, cliente_de, admin):
        html = cliente_de(admin).get(reverse("core:inicio")).content.decode()
        assert reverse("cuentas:usuarios") in html


class TestGestionDeUsuarios:
    """RF-03."""

    def test_crear_usuario_con_rol(self, cliente_de, admin):
        datos = {"nombre": "Lucía Giménez", "username": "lgimenez", "email": "lg@lab.example",
                 "rol": Rol.CONSULTA, "password1": "Clave-larga-789", "password2": "Clave-larga-789"}
        r = cliente_de(admin).post(reverse("cuentas:usuario_crear"), datos)
        assert r.status_code == 302
        u = Usuario.objects.get(username="lgimenez")
        assert u.rol == Rol.CONSULTA and u.check_password("Clave-larga-789")

    def test_desactivar_usuario(self, cliente_de, admin, tecnico):
        datos = {"nombre": tecnico.nombre, "email": tecnico.email, "rol": tecnico.rol}  # sin is_active = desactivar
        cliente_de(admin).post(reverse("cuentas:usuario_editar", args=[tecnico.pk]), datos)
        tecnico.refresh_from_db()
        assert not tecnico.is_active
        assert Usuario.objects.filter(pk=tecnico.pk).exists()  # no se borra

    def test_administrador_no_puede_desactivarse(self, cliente_de, admin):
        datos = {"nombre": admin.nombre, "email": admin.email, "rol": Rol.CONSULTA}
        cliente_de(admin).post(reverse("cuentas:usuario_editar", args=[admin.pk]), datos)
        admin.refresh_from_db()
        assert admin.is_active and admin.rol == Rol.ADMINISTRADOR

    def test_restablecer_contrasena(self, cliente_de, admin, tecnico):
        nueva = "Restablecida-2026"
        r = cliente_de(admin).post(reverse("cuentas:usuario_contrasena", args=[tecnico.pk]),
                                   {"new_password1": nueva, "new_password2": nueva})
        assert r.status_code == 302
        tecnico.refresh_from_db()
        assert tecnico.check_password(nueva)

    def test_solo_datos_personales_indispensables(self):
        """RNF-07: nombre, usuario y correo; sin nombre y apellido separados."""
        campos = {f.name for f in Usuario._meta.get_fields()}
        assert {"nombre", "username", "email"} <= campos
        assert not {"first_name", "last_name"} & campos


class TestConfiguracion:
    def test_valor_inicial_30_dias(self, db):
        assert Configuracion.actual().plazo_aviso_dias == 30

    def test_administrador_cambia_el_plazo(self, cliente_de, admin):
        cliente_de(admin).post(reverse("cuentas:configuracion"), {"plazo_aviso_dias": 45, "hora_envio": "07:30"})
        assert Configuracion.actual().plazo_aviso_dias == 45

    def test_rechaza_plazo_absurdo(self, cliente_de, admin):
        r = cliente_de(admin).post(reverse("cuentas:configuracion"), {"plazo_aviso_dias": 0, "hora_envio": "08:00"})
        assert r.status_code == 200
        assert Configuracion.actual().plazo_aviso_dias == 30
