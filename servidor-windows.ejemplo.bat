@echo off
rem Copia este archivo como servidor.bat y cambia la IP y el puerto de PostgreSQL por los tuyos.
cd /d "%~dp0"
set POSTGRES_PORT=5010
set DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.50
set URL_SISTEMA=http://192.168.1.50:8000
set DJANGO_DEBUG=false
set DJANGO_SSL_REDIRECT=false
set PYTHONUNBUFFERED=1
rem set ANTHROPIC_API_KEY=tu-clave
rem Correo de los avisos. Con Gmail usa una "contrasena de aplicacion" (ver la guia).
rem set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
rem set EMAIL_HOST=smtp.gmail.com
rem set EMAIL_PORT=587
rem set EMAIL_USE_TLS=true
rem set EMAIL_HOST_USER=tu-cuenta@gmail.com
rem set EMAIL_HOST_PASSWORD=la-contrasena-de-aplicacion
rem set DEFAULT_FROM_EMAIL=CalibraLab ^<tu-cuenta@gmail.com^>
.venv\Scripts\python.exe manage.py collectstatic --noinput > servidor.log 2>&1
.venv\Scripts\python.exe servidor.py >> servidor.log 2>&1
