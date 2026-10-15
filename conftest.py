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
