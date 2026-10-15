"""Pruebas del módulo H: registro de cambios (RF-39, RF-40, RNF-12)."""
import pytest
from django.db import DatabaseError, connection, transaction
from django.urls import reverse

from apps.auditoria.models import Accion, RegistroCambio, RegistroInalterableError
from apps.cuentas.models import Configuracion, Rol, Usuario
from conftest import CLAVE


class TestRegistroAutomatico:
    def test_alta_de_usuario(self, cliente_de, admin):
        datos = {"nombre": "Carlos Benítez", "username": "cbenitez", "email": "cb@lab.example",
                 "rol": Rol.TECNICO, "password1": "Clave-larga-789", "password2": "Clave-larga-789"}
        cliente_de(admin).post(reverse("cuentas:usuario_crear"), datos)
        fila = RegistroCambio.objects.get(accion=Accion.ALTA, objeto="Carlos Benítez")
        assert fila.usuario == admin

    def test_modificacion_con_valor_anterior_y_nuevo(self, cliente_de, admin, tecnico):
        datos = {"nombre": tecnico.nombre, "email": tecnico.email, "rol": Rol.CONSULTA, "is_active": "on"}
        cliente_de(admin).post(reverse("cuentas:usuario_editar", args=[tecnico.pk]), datos)
        fila = RegistroCambio.objects.get(accion=Accion.MODIFICACION, objeto_id=str(tecnico.pk))
        assert (fila.campo, fila.valor_anterior, fila.valor_nuevo) == ("rol", "Técnico", "Consulta")
        assert fila.usuario == admin

    def test_desactivar_es_cambio_de_estado(self, cliente_de, admin, tecnico):
        datos = {"nombre": tecnico.nombre, "email": tecnico.email, "rol": tecnico.rol}
        cliente_de(admin).post(reverse("cuentas:usuario_editar", args=[tecnico.pk]), datos)
        fila = RegistroCambio.objects.get(accion=Accion.CAMBIO_ESTADO)
        assert (fila.valor_anterior, fila.valor_nuevo) == ("Sí", "No")

    def test_contrasena_no_queda_visible(self, tecnico):
        tecnico.set_password("Otra-clave-segura-1")
        tecnico.save()
        fila = RegistroCambio.objects.get(accion=Accion.MODIFICACION, objeto_id=str(tecnico.pk))
        assert fila.valor_nuevo == "(cambiado)"
        assert "Otra-clave" not in fila.valor_anterior + fila.valor_nuevo

    def test_cambio_de_configuracion(self, db):
        conf = Configuracion.actual()
        conf.plazo_aviso_dias = 60
        conf.save()
        fila = RegistroCambio.objects.get(accion=Accion.MODIFICACION, modelo="configuración")
        assert (fila.valor_anterior, fila.valor_nuevo) == ("30", "60")

    def test_ingresos_y_fallos(self, client, tecnico):
        client.post(reverse("cuentas:login"), {"username": "tecnico", "password": "mal"})
        client.post(reverse("cuentas:login"), {"username": "tecnico", "password": CLAVE})
        acciones = list(RegistroCambio.objects.order_by("id").values_list("accion", flat=True))
        assert Accion.INGRESO_FALLIDO in acciones and Accion.INGRESO in acciones

    def test_guardar_sin_cambios_no_registra(self, tecnico):
        antes = RegistroCambio.objects.count()
        Usuario.objects.get(pk=tecnico.pk).save()
        assert RegistroCambio.objects.count() == antes


class TestRegistroInalterable:
    """RNF-12: nadie modifica ni borra el registro, tampoco el administrador."""

    @pytest.fixture
    def fila(self, tecnico):
        return RegistroCambio.objects.filter(objeto_id=str(tecnico.pk)).first()

    def test_modelo_no_permite_modificar(self, fila):
        fila.valor_nuevo = "falso"
        with pytest.raises(RegistroInalterableError):
            fila.save()

    def test_modelo_no_permite_borrar(self, fila):
        with pytest.raises(RegistroInalterableError):
            fila.delete()

    @pytest.mark.parametrize("sql", [
        "UPDATE auditoria_registrocambio SET valor_nuevo = 'falso'",
        "DELETE FROM auditoria_registrocambio",
        "TRUNCATE auditoria_registrocambio",
    ])
    def test_base_de_datos_lo_impide(self, fila, sql):
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cur:
            cur.execute(sql)

    def test_queryset_update_tambien_falla(self, fila):
        with pytest.raises(DatabaseError), transaction.atomic():
            RegistroCambio.objects.update(valor_nuevo="falso")

    def test_admin_de_django_es_solo_lectura(self, cliente_de, admin, fila):
        admin.is_staff = admin.is_superuser = True
        admin.save()
        c = cliente_de(admin)
        assert c.get(reverse("admin:auditoria_registrocambio_change", args=[fila.pk])).status_code == 200
        r = c.post(reverse("admin:auditoria_registrocambio_delete", args=[fila.pk]), {"post": "yes"})
        assert r.status_code == 403


class TestConsulta:
    def test_filtrar_por_usuario_y_accion(self, cliente_de, admin, tecnico):
        c = cliente_de(admin)
        r = c.get(reverse("auditoria:lista"), {"accion": Accion.ALTA, "usuario": admin.pk})
        assert r.status_code == 200
        assert all(x.accion == Accion.ALTA and x.usuario_id == admin.pk for x in r.context["registros"])

    def test_filtrar_por_fecha(self, cliente_de, admin):
        r = cliente_de(admin).get(reverse("auditoria:lista"), {"desde": "2000-01-01", "hasta": "2000-01-02"})
        assert list(r.context["registros"]) == []
