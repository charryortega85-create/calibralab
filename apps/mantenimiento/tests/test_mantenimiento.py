from datetime import date

from django.urls import reverse

from apps.mantenimiento.models import EvaluacionEfecto, Novedad, PlanMantenimiento
from apps.mantenimiento.views import evaluaciones_pendientes, tareas_con_vencimiento


def test_plan_y_novedad_cierran_la_tarea(cliente_de, tecnico, crear_equipo):
    e = crear_equipo()
    c = cliente_de(tecnico)
    c.post(reverse("mantenimiento:plan_crear", args=[e.pk]),
           {"actividad": "Verificación con masa de 500 g", "frecuencia_meses": 1, "responsable": tecnico.pk})
    t = PlanMantenimiento.objects.get()
    assert tareas_con_vencimiento(date(2026, 10, 15))[0].atrasada
    c.post(reverse("mantenimiento:novedad_crear", args=[e.pk]),
           {"tipo": "verificacion", "fecha": "2026-10-10", "descripcion": "Lectura 500,02 g", "plan": t.pk,
            "responsable": tecnico.pk})
    n = Novedad.objects.get()
    assert n.plan == t and n.equipo == e
    tarea = tareas_con_vencimiento(date(2026, 10, 15))[0]
    assert tarea.proxima == date(2026, 11, 10) and not tarea.atrasada
    assert "500,02" in c.get(reverse("mantenimiento:indice")).content.decode()


def test_evaluacion_del_efecto_vinculada_al_no_apto(cliente_de, tecnico, crear_equipo, calibrar):
    e = crear_equipo()
    calibrar(e, date(2025, 9, 10))
    s = calibrar(e, date(2026, 9, 14), errores=("0.9", "0", "0"))
    assert list(evaluaciones_pendientes()) == [s]
    c = cliente_de(tecnico)
    url = reverse("mantenimiento:evaluacion", args=[s.pk])
    assert 'value="2025-09-10"' in c.get(url).content.decode()  # propone desde la última conforme
    datos = {"desde": "2025-09-10", "hasta": "2026-09-14", "resultados_revisados": "Informes 101 a 140",
             "conclusion": "con_efecto", "fecha": "2026-09-20"}
    assert c.post(url, datos).status_code == 200  # con efecto exige acciones
    c.post(url, {**datos, "acciones": "Se avisó a los clientes y se repitieron 3 ensayos"})
    ev = EvaluacionEfecto.objects.get()
    assert ev.servicio == s and ev.evaluado_por == tecnico
    assert not evaluaciones_pendientes().exists()
    assert "repitieron" in c.get(url).content.decode()


def test_evaluacion_solo_para_no_aptos(cliente_de, tecnico, crear_equipo, calibrar):
    s = calibrar(crear_equipo(), date(2026, 9, 14))
    assert cliente_de(tecnico).get(reverse("mantenimiento:evaluacion", args=[s.pk])).status_code == 404


def test_consulta_no_registra_novedades(cliente_de, consulta, crear_equipo):
    e = crear_equipo()
    assert cliente_de(consulta).get(reverse("mantenimiento:novedad_crear", args=[e.pk])).status_code == 403
