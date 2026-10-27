from django.db import migrations

from apps.servicios.calculos import sumar_meses


def completar(apps, schema_editor):
    """Las calibraciones no conformes no tenían próxima fecha; ahora cuenta la fecha de cada una (RN-02)."""
    Servicio = apps.get_model("servicios", "Servicio")
    pendientes = Servicio.objects.filter(tipo="calibracion", proxima_fecha__isnull=True).select_related("equipo")
    for s in pendientes:
        s.proxima_fecha_calculada = s.proxima_fecha = sumar_meses(s.fecha, s.equipo.intervalo_meses)
        s.save(update_fields=["proxima_fecha_calculada", "proxima_fecha"])


class Migration(migrations.Migration):

    dependencies = [
        ("servicios", "0005_sin_reconocimiento_de_proveedor"),
    ]

    operations = [
        migrations.RunPython(completar, migrations.RunPython.noop),
    ]
