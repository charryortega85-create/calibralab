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
| B · Inventario y ficha del equipo (RF-05 a RF-14) | Listo |
| C · Calibraciones, calificaciones y certificaciones (RF-15 a RF-24) | Listo |
| D · Estado de calibración y alertas (RF-25 a RF-28) | Listo |
| E · Plan, lotes y presupuesto (RF-29 a RF-33) | Listo |
| F · Mantenimiento y novedades (RF-34, RF-35) | Listo |
| G · Reportes (RF-36 a RF-38) | Listo |

## Puesta en marcha con Docker (lo más simple)

```bash
cp .env.example .env
docker compose up --build
docker compose exec web python manage.py cargar_demo
```

`cargar_demo` crea los usuarios de ejemplo y carga los 36 equipos de la maqueta con sus servicios,
un no apto con su decisión y evaluación, mantenimientos, lotes y el plan 2026. Se puede ejecutar
más de una vez: no duplica datos. Para tener solo los usuarios, usa `crear_usuarios_demo`.

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
python manage.py cargar_demo
python manage.py runserver
```

Para generar la hoja de vida en PDF, WeasyPrint necesita Pango instalado en el sistema
(en Debian o Ubuntu: `apt install libpango-1.0-0 libpangoft2-1.0-0`; en Windows y macOS, ver la
[guía de WeasyPrint](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html)).

## Avisos por correo (RF-28)

Los avisos se envían con un comando que se programa una vez al día, a la hora configurada:

```bash
python manage.py enviar_avisos
```

Por ejemplo, con cron a las 08:00: `0 8 * * * cd /app && python manage.py enviar_avisos`.
En Windows, `servidor.py` los envía solo cada día a la hora de *Configuración*, sin otra tarea.
El servidor de correo se configura con las variables `EMAIL_*` del archivo `.env`; sin ellas, los
correos se muestran en la consola. El Administrador también puede enviarlos desde *Estado y alertas → Avisos por correo*.

## Pruebas automáticas (RNF-24)

Un solo comando ejecuta todas las pruebas:

```bash
pytest
```

## Estructura

```
config/            configuración de Django (settings, urls)
apps/core/         pantalla de inicio, menú por rol, exportación, datos de ejemplo
apps/cuentas/      módulo A: usuarios, roles, permisos, configuración
apps/catalogos/    listas controladas: marcas, ubicaciones, unidades, proveedores (RF-08)
apps/equipos/      módulo B: inventario, ficha, puntos y EMP, importación, etiquetas QR
apps/servicios/    módulo C: calibraciones, calificaciones, certificaciones y cálculos (calculos.py)
apps/alertas/      módulo D: estado de calibración y avisos por correo
apps/plan/         módulo E: lotes, plan anual, ejecución y presupuesto
apps/mantenimiento/ módulo F: plan de mantenimiento, novedades y evaluación del efecto
apps/reportes/     módulo G: hoja de vida en PDF y reportes en Excel o CSV
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
- **Cálculos**: las reglas RN-02 a RN-04 están en funciones puras (`apps/servicios/calculos.py`) con `Decimal`, probadas con los casos del documento y los casos límite (error igual al EMP, vencimiento en el día, aviso en el día exacto) (RNF-11).
- **Estado de calibración**: se calcula, nunca se guarda. Sale solo de las calibraciones: la próxima fecha es la de la última calibración conforme. Un equipo calibrado que nunca fue apto cuenta como vencido. Las calificaciones y certificaciones muestran su propia vigencia.
- **No apto (RN-05)**: el sistema propone pasar el equipo a «fuera de servicio», una persona confirma o justifica mantenerlo, y queda pendiente la evaluación del efecto desde la última calibración conforme (RF-35).
- **Versiones (RN-07, RNF-09)**: los registros no se borran. Cada corrección pide el motivo y guarda la versión anterior (`django-simple-history`), incluidos los certificados adjuntos.
- **Archivo de certificados**: cada servicio guarda su certificado (PDF o foto), las páginas adicionales y los datos del certificado (lugar, condiciones ambientales, procedimiento, patrones utilizados, quién lo realizó y autorizó). En *Certificados* se buscan, se descargan juntos en ZIP para una auditoría y cada uno tiene un QR imprimible. `cargar_demo` genera certificados de ejemplo en PDF (con `--sin-archivos` no los genera).
- **Consulta por QR**: al escanear la etiqueta de un equipo se ve su estado y su historial de servicios; al tocar un servicio, o al escanear el QR de un certificado, se lee el certificado. No hace falta iniciar sesión y es solo lectura (`/qr/...`). El certificado nunca se envía como archivo: cada hoja se convierte en imagen con una marca de agua «SOLO CONSULTA» con fecha y hora, se dibuja en un lienzo, no tiene enlace de descarga ni se puede abrir sola, y la página bloquea el menú de guardar, la impresión y las teclas de copiar e imprimir, y oculta el certificado cuando la ventana pierde el foco (herramienta de recortes). Ninguna página web puede impedir del todo una captura de pantalla del teléfono: por eso la marca de agua. El QR lleva el número del registro firmado con `QR_CLAVE`, así que no se puede abrir otro equipo cambiando la dirección. `URL_SISTEMA` debe ser la dirección con la que los teléfonos llegan al sistema, y `QR_CLAVE` no se cambia una vez impresas las etiquetas.
- **Laboratorios y áreas**: la página Sistema → Laboratorios y áreas muestra cada laboratorio con sus áreas, su encargado y la cantidad de equipos. Cada equipo pertenece a un área. Al Técnico se le marcan sus áreas: ve y registra solo los equipos de esas áreas y los que tiene a su cargo, con sus servicios, avisos, mantenimiento y reportes; un equipo de otra área responde como inexistente. El Administrador, los usuarios de Consulta y el Técnico sin áreas ven todo.
- **Encargado de laboratorio**: rol que el Administrador asigna a uno o más laboratorios. Ve todo lo de sus áreas (también las que el Administrador agregue después) y trabaja con esos equipos como un Técnico. No crea usuarios ni áreas, ni ve otros laboratorios o la configuración: los laboratorios, las áreas y los usuarios los crea solo el Administrador.
- **Lectura de certificados con IA (opcional)**: al registrar un servicio, el botón «Leer el certificado con IA» envía el PDF o la foto del certificado (hasta `IA_MAXIMO_HOJAS` hojas, 3 por defecto) a la API de Anthropic y completa el formulario: tipo, fecha, n.º, proveedor, condiciones, puntos medidos y patrones. Los campos completados quedan marcados en color y no se guarda nada hasta que la persona revisa y pulsa Guardar. Se activa con `ANTHROPIC_API_KEY` (modelo en `IA_MODELO`, por defecto `claude-opus-5-5` con esfuerzo bajo). Cada lectura queda registrada con sus tokens y su costo en Configuración → Ver el registro de lecturas.
- **Sugerencia de intervalo**: la ficha del equipo y el reporte «Revisión de intervalos» sugieren acortar o alargar el intervalo de calibración según el uso de la tolerancia (|error| / EMP del punto peor) y su deriva entre calibraciones aptas, siguiendo la idea de ILAC-G24: acortar a la mitad tras un no apto, acortar si supera el 80 %, no alargar nunca si hay deriva, alargar hasta un 50 % si usa menos del 50 % y es estable, siempre entre 3 y 36 meses. Es una sugerencia: el intervalo lo cambia una persona.
- **Avisos**: cada aviso queda atado a la próxima fecha que lo originó. Al registrar una calibración nueva, la fecha cambia y se deja de avisar; los equipos de baja no se avisan.
