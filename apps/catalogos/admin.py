from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Area, Laboratorio, Marca, Proveedor, TipoInstrumento, Ubicacion, Unidad

for m in (Laboratorio, Area, Marca, Ubicacion, Unidad, Proveedor, TipoInstrumento):
    admin.site.register(m, SimpleHistoryAdmin)
