import csv
import io
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.equipos.models import Equipo, EstadoEquipo


def datos_equipo(catalogo, tecnico, **extra):
    d = {"codigo": "eq-0100", "descripcion": "Balanza analítica 220 g", "marca": catalogo["marca"].pk,
         "modelo": "BA-220", "numero_serie": "SN-1", "ubicacion": catalogo["ubicacion"].pk,
         "responsable": tecnico.pk, "unidad": catalogo["unidad"].pk, "capacidad": "220", "criticidad": "alta",
         "intervalo_meses": 12, "puntos-TOTAL_FORMS": 1, "puntos-INITIAL_FORMS": 0,
         "puntos-0-orden": 1, "puntos-0-valor_nominal": "100", "puntos-0-emp_tipo": "fijo", "puntos-0-emp_valor": "0.001",
         "puntos-0-activo": "on"}
    d.update(extra)
    return d


def test_alta_de_equipo_con_puntos(cliente_de, tecnico, catalogo):
    r = cliente_de(tecnico).post(reverse("equipos:crear"), datos_equipo(catalogo, tecnico))
    e = Equipo.objects.get()
    assert r.status_code == 302 and e.codigo == "EQ-0100" and e.puntos.count() == 1


def test_rn01_codigo_y_serie_unicos(cliente_de, tecnico, catalogo, crear_equipo):
    crear_equipo("EQ-0100", marca=catalogo["marca"], modelo="BA-220", numero_serie="SN-1")
    c = cliente_de(tecnico)
    r = c.post(reverse("equipos:crear"), datos_equipo(catalogo, tecnico, codigo="EQ-0200"))
    assert "RN-01" in r.content.decode()
    r = c.post(reverse("equipos:crear"), datos_equipo(catalogo, tecnico, numero_serie="SN-2"))
    assert r.status_code == 200 and Equipo.objects.count() == 1


def test_emp_pct_alcance_exige_capacidad(cliente_de, tecnico, catalogo):
    r = cliente_de(tecnico).post(reverse("equipos:crear"), datos_equipo(
        catalogo, tecnico, capacidad="", **{"puntos-0-emp_tipo": "pct_alcance"}))
    assert "alcance" in r.content.decode() and not Equipo.objects.exists()


def test_cambio_de_estado_pide_confirmacion_y_registra(cliente_de, tecnico, crear_equipo):
    e = crear_equipo()
    c = cliente_de(tecnico)
    datos = {"estado_nuevo": "baja", "fecha": "2026-10-01", "motivo": "Obsoleto"}
    c.post(reverse("equipos:estado", args=[e.pk]), datos)
    e.refresh_from_db()
    assert e.estado == EstadoEquipo.EN_SERVICIO
    c.post(reverse("equipos:estado", args=[e.pk]), {**datos, "confirmo": "on"})
    e.refresh_from_db()
    assert e.estado == EstadoEquipo.BAJA and e.cambios_estado.get().usuario == tecnico


def test_lista_oculta_bajas_y_filtra_por_estado(cliente_de, consulta, crear_equipo, calibrar):
    a = crear_equipo("EQ-0001")
    crear_equipo("EQ-0002", estado=EstadoEquipo.BAJA)
    crear_equipo("EQ-0003")
    calibrar(a, date(2026, 9, 1))
    c = cliente_de(consulta)
    html = c.get(reverse("equipos:lista")).content.decode()
    assert "EQ-0001" in html and "EQ-0003" in html and "EQ-0002" not in html
    html = c.get(reverse("equipos:lista"), {"estado_cal": "sin_registro"}).content.decode()
    assert "EQ-0003" in html and "EQ-0001" not in html


def test_exportar_inventario(cliente_de, consulta, crear_equipo):
    crear_equipo()
    r = cliente_de(consulta).get(reverse("equipos:lista"), {"formato": "csv"})
    filas = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
    assert filas[1][0] == "EQ-0001"


def test_ficha_y_etiqueta(cliente_de, consulta, crear_equipo):
    e = crear_equipo()
    c = cliente_de(consulta)
    assert "Balanza de precisión" in c.get(e.get_absolute_url()).content.decode()
    assert "<svg" in c.get(reverse("equipos:etiqueta", args=[e.pk])).content.decode()


def test_importar_revisa_y_confirma(cliente_de, tecnico, catalogo):
    c = cliente_de(tecnico)
    contenido = ("codigo;patrimonio;descripcion;marca;modelo;numero_serie;ubicacion;responsable;unidad;rango_min;"
                 "rango_max;resolucion;capacidad;tolerancia;criticidad;intervalo_meses\n"
                 "EQ-0500;;Balanza 1;Marca A;M1;S1;Sala de balanzas;tecnico;g;;;;;;Alta;12\n"
                 "EQ-0501;;Balanza 2;Marca A;M1;S2;Sala de balanzas;tecnico;g;;;;;;Media;6\n")
    r = c.post(reverse("equipos:importar"), {"archivo": SimpleUploadedFile("e.csv", contenido.encode())})
    assert r.status_code == 200 and not Equipo.objects.exists()
    c.post(reverse("equipos:importar"), {"confirmar": "1"})
    assert Equipo.objects.count() == 2


def test_importar_con_errores_no_guarda_nada(cliente_de, tecnico, catalogo):
    c = cliente_de(tecnico)
    contenido = ("codigo;patrimonio;descripcion;marca;modelo;numero_serie;ubicacion;responsable;unidad;rango_min;"
                 "rango_max;resolucion;capacidad;tolerancia;criticidad;intervalo_meses\n"
                 "EQ-0500;;Balanza 1;Marca A;M1;S1;Sala de balanzas;tecnico;g;;;;;;Alta;12\n"
                 "EQ-0500;;Balanza 2;Marca X;M1;S2;Sala de balanzas;tecnico;g;;;;;;Media;6\n")
    r = c.post(reverse("equipos:importar"), {"archivo": SimpleUploadedFile("e.csv", contenido.encode())})
    c.post(reverse("equipos:importar"), {"confirmar": "1"})
    assert r.status_code == 200 and not Equipo.objects.exists()


ARCHIVO_NUEVOS = ("codigo;descripcion;marca;modelo;numero_serie;ubicacion;responsable;unidad;criticidad;intervalo_meses\n"
                  "EQ-0600;Balanza 1;Marca Nueva;M1;S1;Sala Nueva;tecnico;mg;Alta;12\n"
                  "EQ-0601;Balanza 2;marca nueva;M1;S2;Sala Nueva;tecnico;mg;Media;6\n")


def test_importar_sin_listas_avisa_una_vez_por_campo(cliente_de, tecnico, catalogo):
    r = cliente_de(tecnico).post(reverse("equipos:importar"),
                                 {"archivo": SimpleUploadedFile("e.csv", ARCHIVO_NUEVOS.encode())})
    html = r.content.decode()
    assert "Marca Nueva" in html and "obligatorio" not in html
    assert "crear_faltantes" not in html  # el técnico no puede agregar a las listas


def test_administrador_agrega_a_las_listas_al_confirmar(cliente_de, admin, tecnico, catalogo):
    from apps.catalogos.models import Marca, Ubicacion, Unidad

    c = cliente_de(admin)
    r = c.post(reverse("equipos:importar"),
               {"archivo": SimpleUploadedFile("e.csv", ARCHIVO_NUEVOS.encode()), "crear_faltantes": "on"})
    html = r.content.decode()
    assert "Se agregará la marca «Marca Nueva» a la lista." in html and "Guardar 2 equipos" in html
    assert not Marca.objects.filter(nombre="Marca Nueva").exists()  # la revisión no guarda nada
    c.post(reverse("equipos:importar"), {"confirmar": "1"})
    assert Equipo.objects.filter(codigo__in=["EQ-0600", "EQ-0601"]).count() == 2
    assert Marca.objects.filter(nombre__iexact="marca nueva").count() == 1
    assert Ubicacion.objects.filter(nombre="Sala Nueva").exists() and Unidad.objects.filter(simbolo="mg").exists()


def test_administrador_agrega_laboratorio_y_area_desde_el_archivo(cliente_de, admin, tecnico, catalogo):
    from apps.catalogos.models import Area

    contenido = ("codigo;descripcion;marca;modelo;numero_serie;laboratorio;area;ubicacion;responsable;unidad\n"
                 "EEB-09;Balanza;CAPTAR CHEM;M1;S1;Direccion de Zoonosis;EEB;Laboratorio EEB;tecnico;g\n")
    c = cliente_de(admin)
    r = c.post(reverse("equipos:importar"), {"archivo": SimpleUploadedFile("e.csv", contenido.encode()),
                                             "crear_faltantes": "on"})
    assert "Se agregará el área «EEB» a Direccion de Zoonosis." in r.content.decode()
    c.post(reverse("equipos:importar"), {"confirmar": "1"})
    assert Equipo.objects.get(codigo="EEB-09").area == Area.objects.get(nombre="EEB", laboratorio__nombre="Direccion de Zoonosis")


def test_encargado_agrega_areas_solo_en_su_laboratorio(cliente_de, catalogo):
    from apps.catalogos.models import Area, Laboratorio
    from apps.cuentas.models import Rol
    from conftest import _crear

    Laboratorio.objects.create(nombre="Ajeno")
    enc = _crear("enc", Rol.ENCARGADO)
    enc.laboratorios.set([Laboratorio.objects.create(nombre="Propio")])
    contenido = ("codigo;descripcion;marca;modelo;numero_serie;laboratorio;area;ubicacion;responsable;unidad\n"
                 "EQ-0700;Balanza;Marca A;M1;S1;Propio;Nueva;Sala de balanzas;enc;g\n"
                 "EQ-0701;Balanza;Marca A;M1;S2;Ajeno;Otra;Sala de balanzas;enc;g\n"
                 "EQ-0702;Balanza;Marca A;M1;S3;Inventado;Otra;Sala de balanzas;enc;g\n")
    r = cliente_de(enc).post(reverse("equipos:importar"), {"archivo": SimpleUploadedFile("e.csv", contenido.encode()),
                                                           "crear_faltantes": "on"})
    html = r.content.decode()
    assert "Se agregará el área «Nueva» a Propio." in html
    assert "«Ajeno» no está a tu cargo" in html and "«Inventado» no está a tu cargo" in html
    assert not Area.objects.filter(nombre="Nueva").exists()
