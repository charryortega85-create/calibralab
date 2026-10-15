from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Marca, Proveedor, Ubicacion, Unidad

for m in (Marca, Ubicacion, Unidad, Proveedor):
    admin.site.register(m, SimpleHistoryAdmin)
