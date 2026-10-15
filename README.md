# CalibraLab

Sistema web de gestión de calibraciones, calificaciones y certificaciones de equipos de laboratorio.
Trabajo Final de Grado. Python + Django 5.2 + PostgreSQL 16, interfaz con plantillas de Django.

Los requerimientos (RF, RN, RNF) están en el documento «Requerimientos del sistema» (apartados II.1.3 a II.1.8 de la memoria).
Todos los datos son inventados.

## Estado

| Módulo | Estado |
|---|---|
| A · Acceso y usuarios (RF-01 a RF-04, RF-27) | Listo |
| H · Registro de cambios (RF-39, RF-40) | Listo |
| B · Inventario y ficha del equipo | Pendiente |
| C · Calibraciones, calificaciones y certificaciones | Pendiente |
| D · Estado de calibración y alertas | Pendiente |
| E · Plan, lotes y presupuesto | Pendiente |
| F · Mantenimiento y novedades | Pendiente |
| G · Reportes | Pendiente |

## Puesta en marcha con Docker (lo más simple)

```bash
cp .env.example .env
docker compose up --build
docker compose exec web python manage.py crear_usuarios_demo
```

Abre http://localhost:8000 e ingresa con `mperez` / `Calibra-2026` (Administrador).
Otros usuarios de ejemplo: `lgimenez`, `cbenitez`, `aduarte` (Técnico) y `auditor` (Consulta), con la misma contraseña.

## Puesta en marcha sin Docker

Necesitas Python 3.12 o superior y PostgreSQL 16 con una base `calibralab` y un usuario `calibralab` con permiso para crear bases (las pruebas crean la suya).

```bash
python -m venv .venv
source .venv/bin/activate          # En Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env               # y exporta las variables, o edítalas en tu entorno
python manage.py migrate
python manage.py crear_usuarios_demo
python manage.py runserver
```

## Pruebas automáticas (RNF-24)

Un solo comando ejecuta todas las pruebas:

```bash
pytest
```

## Estructura

```
config/            configuración de Django (settings, urls)
apps/core/         pantalla de inicio, menú por rol, páginas de error
apps/cuentas/      módulo A: usuarios, roles, permisos, configuración
apps/auditoria/    módulo H: registro de cambios automático e inalterable
templates/         plantillas HTML (diseño tomado de la maqueta del panel)
static/            CSS y JavaScript propios, sin librerías externas
```

Cada módulo del sistema es una app de Django separada, con sus propias pruebas (RNF-23).

## Decisiones de diseño

- **Tres roles** (Técnico, Administrador, Consulta). Los permisos se comprueban en el servidor en cada pantalla: escribir a mano una dirección no autorizada devuelve «acceso denegado» (RNF-03).
- **Usuarios**: solo nombre, usuario y correo (RNF-07). No se borran; se desactivan (RF-03).
- **Seguridad**: contraseñas de 10 caracteres o más guardadas con hash (RNF-02); sesión de 20 minutos sin actividad y bloqueo de 15 minutos tras 5 intentos fallidos con `django-axes` (RNF-05); HTTPS obligatorio con `DJANGO_DEBUG=false` (RNF-04).
- **Registro de cambios**: cada módulo declara sus modelos con `auditar(...)` y las altas, modificaciones (valor anterior y nuevo), cambios de estado e ingresos se registran solos (RF-39). La tabla solo admite inserciones: lo impide el modelo y también un trigger de PostgreSQL (RNF-12).
- **Transacciones**: cada petición se guarda completa o no se guarda (`ATOMIC_REQUESTS`, RNF-10).
