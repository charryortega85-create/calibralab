"""
Configuración de CalibraLab.

Los valores que cambian entre instalaciones (claves, base de datos, correo) se leen de
variables de entorno; ver `.env.example`. Así el mismo código sirve para desarrollo,
pruebas y el servidor de demostración (RNF-26).
"""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(nombre, defecto=None):
    return os.environ.get(nombre, defecto)


def env_bool(nombre, defecto=False):
    return env(nombre, str(defecto)).lower() in ("1", "true", "si", "sí", "yes")


SECRET_KEY = env("DJANGO_SECRET_KEY", "solo-para-desarrollo-cambiar-en-produccion")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in env("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",
    "simple_history",
    "apps.core",
    "apps.cuentas",
    "apps.auditoria",
    "apps.catalogos",
    "apps.equipos",
    "apps.servicios",
    "apps.alertas",
    "apps.plan",
    "apps.mantenimiento",
    "apps.reportes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Sirve el CSS y el JavaScript con gunicorn (Docker y servidor), sin depender de DEBUG.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.auditoria.middleware.UsuarioActualMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    # Axes va al final: bloquea el acceso tras varios intentos fallidos (RNF-05).
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.menu",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "calibralab"),
        "USER": env("POSTGRES_USER", "calibralab"),
        "PASSWORD": env("POSTGRES_PASSWORD", "calibralab"),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
        # Cada petición se guarda completa o no se guarda (RNF-10).
        "ATOMIC_REQUESTS": True,
    }
}

# --- Acceso y usuarios (módulo A) -------------------------------------------------
AUTH_USER_MODEL = "cuentas.Usuario"
LOGIN_URL = "cuentas:login"
LOGIN_REDIRECT_URL = "core:inicio"
LOGOUT_REDIRECT_URL = "cuentas:login"
# RF-04: el enlace para recuperar la contraseña vence a las 24 horas (y sirve una sola vez).
PASSWORD_RESET_TIMEOUT = int(env("RECUPERAR_HORAS", "24")) * 3600

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# RNF-02: contraseñas de al menos 10 caracteres, guardadas con hash (nadie puede leerlas).
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# RNF-05: la sesión se cierra tras 20 minutos sin actividad.
SESSION_COOKIE_AGE = int(env("SESION_MINUTOS", "20")) * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# RNF-05: 5 intentos fallidos seguidos bloquean al usuario durante 15 minutos.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_RESET_ON_SUCCESS = True
# Se bloquea el usuario atacado y también la dirección IP que prueba muchos usuarios.
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
AXES_LOCKOUT_TEMPLATE = "registration/bloqueado.html"

# --- Seguridad en el servidor (RNF-04, RNF-06) ---------------------------------------
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # En la red local sin HTTPS (DJANGO_SSL_REDIRECT=false) las cookies seguras impedirían iniciar sesión.
    if SECURE_SSL_REDIRECT:
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True
        SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# --- Idioma y zona horaria (RNF-14) --------------------------------------------------
LANGUAGE_CODE = "es"
TIME_ZONE = env("DJANGO_TIME_ZONE", "America/Asuncion")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = Path(env("DJANGO_MEDIA_ROOT", BASE_DIR / "media"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Correo (avisos de vencimiento, RF-28) --------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "CalibraLab <avisos@calibralab.example>")

# --- Archivos adjuntos (certificados, documentos) -------------------------------------
# Se sirven solo a usuarios con sesión iniciada (ver apps.core.views.archivo).
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
TAMANO_MAXIMO_ADJUNTO_MB = int(env("TAMANO_MAXIMO_ADJUNTO_MB", "20"))
EXTENSIONES_PERMITIDAS = ["pdf", "jpg", "jpeg", "png", "webp", "doc", "docx", "xls", "xlsx"]

# Dirección pública del sistema, para los enlaces de los correos y de la etiqueta QR (RF-14).
URL_SISTEMA = env("URL_SISTEMA", "http://localhost:8000")
# Firma de los códigos QR. Si se cambia, los QR ya impresos dejan de abrir la consulta.
QR_CLAVE = env("QR_CLAVE", SECRET_KEY)

# --- Lectura de certificados con IA (opcional) -----------------------------------------
# Se activa solo si hay una clave de la API de Anthropic. El contenido del certificado se
# envía a ese servicio; una persona revisa siempre los datos antes de guardar.
IA_CLAVE = env("ANTHROPIC_API_KEY", "")
IA_MODELO = env("IA_MODELO", "claude-opus-5-5")
IA_MAXIMO_HOJAS = int(env("IA_MAXIMO_HOJAS", "3"))
# Dólares por millón de tokens (entrada, salida), para el registro de costos.
IA_PRECIOS = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
