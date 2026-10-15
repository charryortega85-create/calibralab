from django.urls import path

from . import views

app_name = "plan"

urlpatterns = [
    path("", views.indice, name="indice"),
    path("prioridad/", views.prioridad, name="prioridad"),
    path("lotes/nuevo/", views.lote_editar, name="lote_crear"),
    path("lotes/<int:pk>/", views.lote, name="lote"),
    path("lotes/<int:pk>/editar/", views.lote_editar, name="lote_editar"),
    path("planes/nuevo/", views.plan_editar, name="plan_crear"),
    path("planes/<int:pk>/", views.plan, name="plan"),
    path("planes/<int:pk>/editar/", views.plan_editar, name="plan_editar"),
    path("planes/<int:plan_pk>/lotes/nuevo/", views.item_editar, name="item_crear"),
    path("planes/<int:plan_pk>/lotes/<int:pk>/", views.item_editar, name="item_editar"),
    path("ejecucion/<int:pk>/", views.ejecucion, name="ejecucion"),
]
