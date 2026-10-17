from decimal import Decimal as D

from django.urls import reverse

from apps.plan.models import EstadoEjecucion, ItemPlan, Lote, PlanAnual


def test_avance_del_plan_y_del_presupuesto(crear_equipo, catalogo):
    plan = PlanAnual.objects.create(ejercicio=2026)
    for i, (est, previsto, pagado) in enumerate([("ejecutado", 4_000_000, 4_000_000), ("programado", 6_000_000, 0)]):
        lote = Lote.objects.create(codigo=f"L-{i}", nombre="x", trabajos="x")
        ItemPlan.objects.create(plan=plan, lote=lote, mes_previsto=3, monto_previsto=previsto,
                                estado_ejecucion=est, monto_pagado=pagado)
    a = plan.avance()
    assert (a["programados"], a["ejecutados"], a["pct_plan"]) == (2, 1, 50)
    assert a["previsto"] == D(10_000_000) and a["pct_presupuesto"] == 40


def test_flujo_lote_plan_y_ejecucion(cliente_de, tecnico, crear_equipo, catalogo):
    e = crear_equipo()
    c = cliente_de(tecnico)
    c.post(reverse("plan:lote_crear"), {"codigo": "l-01", "nombre": "Balanzas", "trabajos": "Calibración en sitio",
                                        "proveedor": catalogo["proveedor"].pk, "costo_estimado": 1000, "equipos": [e.pk]})
    lote = Lote.objects.get(codigo="L-01")
    assert list(lote.equipos.all()) == [e]
    c.post(reverse("plan:plan_crear"), {"ejercicio": 2026, "descripcion": "Programa 2026"})
    plan = PlanAnual.objects.get()
    c.post(reverse("plan:item_crear", args=[plan.pk]), {"lote": lote.pk, "mes_previsto": 3, "monto_previsto": 1000})
    item = ItemPlan.objects.get()
    assert item.proveedor == catalogo["proveedor"]
    # RF-31: ejecutado exige fecha; pagado exige monto
    r = c.post(reverse("plan:ejecucion", args=[item.pk]), {"estado_ejecucion": "ejecutado", "estado_pago": "pagado",
                                                           "monto_pagado": 0, "motivo": "Avance"})
    assert r.status_code == 200
    c.post(reverse("plan:ejecucion", args=[item.pk]), {"estado_ejecucion": "ejecutado", "fecha_ejecucion": "2026-03-10",
                                                       "estado_pago": "pagado", "monto_pagado": 950, "motivo": "Avance"})
    item.refresh_from_db()
    assert item.estado_ejecucion == EstadoEjecucion.EJECUTADO and item.monto_pagado == 950
    assert "L-01" in c.get(plan.get_absolute_url()).content.decode()


def test_prioridad_sugerida(cliente_de, consulta, crear_equipo):
    crear_equipo()
    assert "EQ-0001" in cliente_de(consulta).get(reverse("plan:prioridad")).content.decode()


def test_consulta_no_edita_el_plan(cliente_de, consulta):
    assert cliente_de(consulta).get(reverse("plan:lote_crear")).status_code == 403
