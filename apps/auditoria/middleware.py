"""Guarda quién hace la petición para que las señales sepan a quién atribuir cada cambio."""
from contextvars import ContextVar

_peticion = ContextVar("peticion_actual", default=None)


def peticion_actual():
    return _peticion.get()


def usuario_actual():
    peticion = _peticion.get()
    usuario = getattr(peticion, "user", None)
    return usuario if usuario is not None and usuario.is_authenticated else None


def ip_de(peticion):
    if peticion is None:
        return None
    reenviada = peticion.META.get("HTTP_X_FORWARDED_FOR")
    return reenviada.split(",")[0].strip() if reenviada else peticion.META.get("REMOTE_ADDR")


class UsuarioActualMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _peticion.set(request)
        try:
            return self.get_response(request)
        finally:
            _peticion.reset(token)
