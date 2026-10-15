import pytest

from apps.cuentas.models import Rol, Usuario

CLAVE = "Clave-de-prueba-123"


def _crear(username, rol, **extra):
    return Usuario.objects.create_user(
        username=username, password=CLAVE, nombre=username.title(), email=f"{username}@lab.example", rol=rol, **extra
    )


@pytest.fixture(autouse=True)
def _cache_limpia(db):
    # Axes guarda los intentos fallidos; cada prueba empieza de cero.
    from axes.utils import reset

    reset()


@pytest.fixture
def admin(db):
    return _crear("admin", Rol.ADMINISTRADOR)


@pytest.fixture
def tecnico(db):
    return _crear("tecnico", Rol.TECNICO)


@pytest.fixture
def consulta(db):
    return _crear("consulta", Rol.CONSULTA)


@pytest.fixture
def cliente_de(client):
    def ingresar(usuario):
        client.force_login(usuario, backend="django.contrib.auth.backends.ModelBackend")
        return client

    return ingresar


# --- Datos para los módulos B a G ------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _archivos_en_temporal(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture
def catalogo(db):
    from apps.catalogos.models import Marca, Proveedor, Ubicacion, Unidad

    return {
        "marca": Marca.objects.create(nombre="Marca A"),
        "ubicacion": Ubicacion.objects.create(nombre="Sala de balanzas"),
        "unidad": Unidad.objects.create(nombre="gramo", simbolo="g", magnitud="masa"),
        "proveedor": Proveedor.objects.create(nombre="Proveedor Y"),
    }


@pytest.fixture
def crear_equipo(catalogo, tecnico):
    """Crea un equipo con puntos de calibración: por defecto, la balanza del ejemplo (EMP ±0,5 g)."""
    from decimal import Decimal

    from apps.equipos.models import Equipo, PuntoCalibracion

    def crear(codigo="EQ-0001", puntos=((100, "fijo", "0.5"), (500, "fijo", "0.5"), (1000, "fijo", "0.5")), **kw):
        datos = {"descripcion": "Balanza de precisión 1000 g", "marca": catalogo["marca"], "modelo": "B-1000",
                 "numero_serie": f"SN-{codigo}", "ubicacion": catalogo["ubicacion"], "responsable": tecnico,
                 "unidad": catalogo["unidad"], "capacidad": Decimal("1000"), "intervalo_meses": 12, "criticidad": "alta"}
        datos.update(kw)
        e = Equipo.objects.create(codigo=codigo, **datos)
        for i, (nominal, tipo, emp) in enumerate(puntos, start=1):
            PuntoCalibracion.objects.create(equipo=e, orden=i, valor_nominal=Decimal(str(nominal)), emp_tipo=tipo,
                                            emp_valor=Decimal(emp))
        return e

    return crear


@pytest.fixture
def calibrar(catalogo):
    """Registra una calibración directamente en la base (sin pasar por la pantalla)."""
    from decimal import Decimal

    from apps.servicios.models import PuntoMedido, Servicio

    def registrar(equipo, fecha, errores=("0.2", "-0.3", "0.4"), incertidumbre=None, regla="simple", numero="CC-1"):
        s = Servicio.objects.create(equipo=equipo, fecha=fecha, proveedor=catalogo["proveedor"], regla=regla,
                                    numero_certificado=numero, registrado_por=equipo.responsable)
        for i, (p, err) in enumerate(zip(equipo.puntos.all(), errores), start=1):
            PuntoMedido.objects.create(servicio=s, orden=i, valor_referencia=p.valor_nominal,
                                       valor_leido=p.valor_nominal + Decimal(err),
                                       incertidumbre=Decimal(incertidumbre) if incertidumbre else None,
                                       emp_tipo=p.emp_tipo, emp_valor=p.emp_valor)
        s.recalcular()
        return s

    return registrar
