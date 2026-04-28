# pytest-django
from unittest import mock

import pytest
from django.test import Client, override_settings

from core.models import ModuloCompletado, ProgresoEstudiante
from formulario.agent import manejar_mensaje_formulario, parsear_respuesta, iniciar_sesion_formulario
from formulario.calculadora import calcular_balance_gei, generar_mensaje_resultado_whatsapp, persistir_resultado_gei
from formulario.factories import ClienteFactory, CursoFactory, EstudianteFactory, ModuloFactory
from formulario.hooks import intentar_iniciar_formulario_al_completar_modulo
from formulario.models import CAMPOS_GEI_7, FichaGEI, FlujoPregunta, ResultadoGEI, SesionFormulario, TipoFormulario
from formulario.routing import debe_usar_agente_formulario


pytestmark = pytest.mark.django_db


def test_ficha_gei_completitud_vacia():
    e = EstudianteFactory()
    f = FichaGEI.objects.create(estudiante=e, curso=CursoFactory())
    assert f.completitud_pct == 0


def test_ficha_gei_completitud_parcial():
    e = EstudianteFactory()
    c = CursoFactory()
    f = FichaGEI.objects.create(
        estudiante=e,
        curso=c,
        area_ha=1.0,
        num_plantas=100,
        fertilizante_kg=10.0,
    )
    assert f.completitud_pct == 42  # 3/7
    f.concentracion_n_pct = 2.0
    f.produccion_kg = 50.0
    f.energia_kwh = 30.0
    f.nombre_finca = "Finca A"
    f.save()
    assert f.completitud_pct == 100


def test_ficha_gei_completitud_total():
    e = EstudianteFactory()
    c = CursoFactory()
    f = FichaGEI.objects.create(
        estudiante=e,
        curso=c,
        nombre_finca="La Esperanza",
        area_ha=1.0,
        num_plantas=100,
        fertilizante_kg=10.0,
        concentracion_n_pct=12.0,
        produccion_kg=200.0,
        energia_kwh=50.0,
    )
    assert f.completitud_pct == 100


def test_parseo_numero_directo():
    p = FlujoPregunta(
        tipo_dato="float", usar_llm_parseo=False, rango_min=None, rango_max=None, campo_destino="area_ha"
    )
    v = parsear_respuesta("120", p)
    assert v == 120.0


@mock.patch("formulario.agent._llm_extrae_numero", return_value=75.0)
def test_parseo_arrobas_llm(m_llm):
    p = FlujoPregunta(
        tipo_dato="float", usar_llm_parseo=True, unidad_parseo="kg", campo_destino="fertilizante_kg"
    )
    v = parsear_respuesta("3 arrobas", p)
    assert v == 75.0
    m_llm.assert_called_once()


def test_validacion_rango_falla():
    c = ClienteFactory()
    e = EstudianteFactory(cliente=c)
    cur = CursoFactory()
    ficha = FichaGEI.objects.create(estudiante=e, curso=cur, cliente=c)
    tf = TipoFormulario.objects.create(
        nombre="Ficha test", curso=cur, modulo=ModuloFactory(curso=cur, numero=1)
    )
    p = FlujoPregunta.objects.create(
        formulario=tf,
        orden=0,
        campo_destino="fertilizante_kg",
        pregunta_texto="¿Cuánto fertilizó?",
        tipo_dato="float",
        rango_min=0,
        rango_max=5000,
        texto_reintento="Pruebe con un valor entre 0 y 5000, por favor.",
    )
    sesion = SesionFormulario.objects.create(
        estudiante=e, formulario=tf, paso_actual=0, ficha=ficha, progreso=None, modulo_siguiente=None
    )
    r = manejar_mensaje_formulario(e, "9999")
    assert p.texto_reintento in r or "5000" in r
    sesion.refresh_from_db()
    assert sesion.paso_actual == 0
    assert sesion.reintentos_paso == 1


def test_validacion_rango_pasa():
    c = ClienteFactory()
    e = EstudianteFactory(cliente=c)
    cur = CursoFactory()
    ficha = FichaGEI.objects.create(estudiante=e, curso=cur, cliente=c)
    m1 = ModuloFactory(curso=cur, numero=1)
    tf = TipoFormulario.objects.create(nombre="F", curso=cur, modulo=m1)
    FlujoPregunta.objects.create(
        formulario=tf,
        orden=0,
        campo_destino="fertilizante_kg",
        pregunta_texto="Fertilizante (kg)?",
        tipo_dato="float",
        rango_min=0,
        rango_max=5000,
    )
    # Segundo paso: si solo hay un paso, al responder se cierra la sesión (completado=True).
    FlujoPregunta.objects.create(
        formulario=tf,
        orden=1,
        campo_destino="area_ha",
        pregunta_texto="Área (ha)?",
        tipo_dato="float",
    )
    SesionFormulario.objects.create(
        estudiante=e, formulario=tf, paso_actual=0, ficha=ficha, progreso=None, modulo_siguiente=None
    )
    manejar_mensaje_formulario(e, "120")
    ficha.refresh_from_db()
    assert ficha.fertilizante_kg == 120.0
    assert SesionFormulario.objects.get(estudiante=e, completado=False).paso_actual == 1


def test_flujo_completo_7_pasos():
    c = ClienteFactory()
    e = EstudianteFactory(cliente=c)
    cur = CursoFactory()
    ficha = FichaGEI.objects.create(estudiante=e, curso=cur, cliente=c)
    m0 = ModuloFactory(curso=cur, numero=1)
    tf = TipoFormulario.objects.create(nombre="7 pasos", curso=cur, modulo=m0)
    campos = list(CAMPOS_GEI_7)
    for i, campo in enumerate(campos):
        FlujoPregunta.objects.create(
            formulario=tf,
            orden=i,
            campo_destino=campo,
            pregunta_texto=f"Indique dato {campo}, por favor.",
            tipo_dato="text" if campo == "nombre_finca" else "float",
        )
    ses = SesionFormulario.objects.create(
        estudiante=e, formulario=tf, paso_actual=0, ficha=ficha, progreso=None, modulo_siguiente=None
    )
    respuestas = [
        "Finca El Roble",
        "2.5",
        "120",
        "50",
        "12",
        "800",
        "35",
    ]
    for _txt in respuestas:
        r = manejar_mensaje_formulario(e, _txt)
        assert "Pregunta" in r or "concluimos" in r or "avanzar" in r or "Escriba" in r
    s = SesionFormulario.objects.get(pk=ses.pk)
    ficha.refresh_from_db()
    assert s.completado
    assert ficha.nombre_finca == "Finca El Roble"
    assert ficha.area_ha == 2.5
    assert ficha.fertilizante_kg == 50.0
    assert ficha.concentracion_n_pct == 12.0
    assert ficha.produccion_kg == 800.0
    assert ficha.energia_kwh == 35.0
    assert ficha.num_plantas == 120


def test_paso_opcional_omitir():
    c = ClienteFactory()
    e = EstudianteFactory(cliente=c)
    cur = CursoFactory()
    ficha = FichaGEI.objects.create(estudiante=e, curso=cur, cliente=c)
    m0 = ModuloFactory(curso=cur, numero=1)
    tf = TipoFormulario.objects.create(nombre="Omitir", curso=cur, modulo=m0)
    FlujoPregunta.objects.create(
        formulario=tf,
        orden=0,
        campo_destino="fertilizante_kg",
        pregunta_texto="Fertilizante (opcional)",
        tipo_dato="float",
        es_opcional=True,
    )
    FlujoPregunta.objects.create(
        formulario=tf,
        orden=1,
        campo_destino="area_ha",
        pregunta_texto="Área (ha)?",
        tipo_dato="float",
    )
    SesionFormulario.objects.create(
        estudiante=e, formulario=tf, paso_actual=0, ficha=ficha, progreso=None, modulo_siguiente=None
    )
    manejar_mensaje_formulario(e, "OMITIR")
    ficha.refresh_from_db()
    assert ficha.fertilizante_kg is None
    assert SesionFormulario.objects.get().paso_actual == 1


def test_reintento_maximo():
    c = ClienteFactory()
    e = EstudianteFactory(cliente=c)
    cur = CursoFactory()
    ficha = FichaGEI.objects.create(estudiante=e, curso=cur, cliente=c)
    m0 = ModuloFactory(curso=cur, numero=1)
    tf = TipoFormulario.objects.create(nombre="R3", curso=cur, modulo=m0)
    FlujoPregunta.objects.create(
        formulario=tf,
        orden=0,
        campo_destino="fertilizante_kg",
        pregunta_texto="Dato 0-10",
        tipo_dato="float",
        rango_min=0,
        rango_max=10,
        es_opcional=False,
        texto_reintento="No válido, repita.",
    )
    FlujoPregunta.objects.create(
        formulario=tf,
        orden=1,
        campo_destino="area_ha",
        pregunta_texto="Área (ha)?",
        tipo_dato="float",
    )
    sesion = SesionFormulario.objects.create(
        estudiante=e, formulario=tf, paso_actual=0, ficha=ficha, progreso=None, modulo_siguiente=None
    )
    for _ in range(3):
        manejar_mensaje_formulario(e, "9999")
    sesion.refresh_from_db()
    assert sesion.paso_actual == 1
    ficha.refresh_from_db()
    assert ficha.fertilizante_kg is None


def test_sesion_no_existe():
    e = EstudianteFactory()
    assert not debe_usar_agente_formulario(e)


def test_sesion_activa():
    c = ClienteFactory()
    e = EstudianteFactory(cliente=c)
    cur = CursoFactory()
    ficha = FichaGEI.objects.create(estudiante=e, curso=cur, cliente=c)
    m0 = ModuloFactory(curso=cur, numero=1)
    tf = TipoFormulario.objects.create(nombre="A", curso=cur, modulo=m0)
    FlujoPregunta.objects.create(
        formulario=tf, orden=0, campo_destino="area_ha", pregunta_texto="Área?", tipo_dato="float"
    )
    SesionFormulario.objects.create(
        estudiante=e, formulario=tf, paso_actual=0, ficha=ficha, completado=False, progreso=None, modulo_siguiente=None
    )
    assert debe_usar_agente_formulario(e)


def test_sesion_completada_no_bloquea():
    c = ClienteFactory()
    e = EstudianteFactory(cliente=c)
    cur = CursoFactory()
    ficha = FichaGEI.objects.create(estudiante=e, curso=cur, cliente=c)
    m0 = ModuloFactory(curso=cur, numero=1)
    tf = TipoFormulario.objects.create(nombre="A", curso=cur, modulo=m0)
    SesionFormulario.objects.create(
        estudiante=e,
        formulario=tf,
        paso_actual=0,
        ficha=ficha,
        completado=True,
        progreso=None,
        modulo_siguiente=None,
    )
    assert not debe_usar_agente_formulario(e)


@override_settings(
    TWILIO_ACCOUNT_SID="ACtest",
    TWILIO_AUTH_TOKEN="tok",
    TWILIO_PHONE_NUMBER="whatsapp:+15550001111",
    BOT_COMERCIAL_WHATSAPP_NUMBER="",
    BOT_COMERCIAL_FORCE_ROUTING=False,
    # Si DJANGO_DEBUG=False en .env, SecurityMiddleware redirige HTTP→HTTPS y el POST no llega al view.
    SECURE_SSL_REDIRECT=False,
)
@mock.patch("formulario.agent.manejar_mensaje_formulario", return_value="[FORMULARIO-OK]")
def test_mensaje_entrante_con_sesion_activa(m_maneja):
    c = ClienteFactory()
    e = EstudianteFactory(
        cliente=c, telefono="573000099991", acepto_terminos=True, estado_chat="ACTIVO", estado_onboarding="completado"
    )
    cur = CursoFactory()
    ficha = FichaGEI.objects.create(estudiante=e, curso=cur, cliente=c)
    m0 = ModuloFactory(curso=cur, numero=1)
    tf = TipoFormulario.objects.create(nombre="A", curso=cur, modulo=m0)
    FlujoPregunta.objects.create(
        formulario=tf, orden=0, campo_destino="area_ha", pregunta_texto="Área?", tipo_dato="float"
    )
    SesionFormulario.objects.create(
        estudiante=e, formulario=tf, paso_actual=0, ficha=ficha, completado=False, progreso=None, modulo_siguiente=None
    )
    with mock.patch("formulario.routing.debe_usar_agente_formulario", return_value=True):
        cl = Client()
        r = cl.post(
            "/webhook/whatsapp/",
            {
                "From": "whatsapp:573000099991",
                "To": "whatsapp:+15550001111",
                "Body": "hola",
            },
            HTTP_HOST="127.0.0.1",
            secure=True,
        )
        assert r.status_code == 200, (r.status_code, r.get("Location", b"")[:200])
    m_maneja.assert_called_once()
    a, b = m_maneja.call_args[0]
    assert b == "hola"


def test_inicio_sesion_desde_modulo():
    c = ClienteFactory()
    e = EstudianteFactory(cliente=c)
    cur = CursoFactory()
    m1 = ModuloFactory(curso=cur, numero=1)
    m2 = ModuloFactory(curso=cur, numero=2)
    m3 = ModuloFactory(curso=cur, numero=3)
    m4 = ModuloFactory(curso=cur, numero=4)
    m5 = ModuloFactory(curso=cur, numero=5)
    TipoFormulario.objects.create(
        nombre="Ficha al salir de m4",
        curso=cur,
        modulo=m4,
        activo=True,
    )
    FlujoPregunta.objects.create(
        formulario=TipoFormulario.objects.get(nombre="Ficha al salir de m4"),
        orden=0,
        campo_destino="area_ha",
        pregunta_texto="Indique su área, por favor.",
        tipo_dato="float",
    )
    p = ProgresoEstudiante.objects.create(
        estudiante=e, curso=cur, modulo_actual=m4, completado=False
    )
    msg = intentar_iniciar_formulario_al_completar_modulo(
        e, p, m4, m5
    )
    assert msg and "Necesitamos" in msg
    assert SesionFormulario.objects.filter(estudiante=e, completado=False).exists()


def _bootstrap_curso_modulos():
    cur = CursoFactory()
    m4 = ModuloFactory(curso=cur, numero=4)
    m5 = ModuloFactory(curso=cur, numero=5)
    return cur, m4, m5


def _crear_tf_con_paso(*, nombre, curso, modulo, cliente=None, pregunta="Indique su área."):
    tf = TipoFormulario.objects.create(
        nombre=nombre,
        curso=curso,
        modulo=modulo,
        cliente=cliente,
        activo=True,
    )
    FlujoPregunta.objects.create(
        formulario=tf,
        orden=0,
        campo_destino="area_ha",
        pregunta_texto=pregunta,
        tipo_dato="float",
    )
    return tf


def test_filtro_cliente_especifico_tiene_prioridad():
    """Si existe un TF para el cliente del estudiante y otro global, gana el del cliente."""
    cliente_a = ClienteFactory(nombre="Nitrofert")
    cliente_b = ClienteFactory(nombre="Otra")
    cur, m4, m5 = _bootstrap_curso_modulos()
    _crear_tf_con_paso(nombre="GEI Global", curso=cur, modulo=m4, cliente=None, pregunta="Pregunta global.")
    _crear_tf_con_paso(
        nombre="GEI Nitrofert", curso=cur, modulo=m4, cliente=cliente_a,
        pregunta="Pregunta específica Nitrofert.",
    )

    estudiante = EstudianteFactory(cliente=cliente_a)
    progreso = ProgresoEstudiante.objects.create(
        estudiante=estudiante, curso=cur, modulo_actual=m4, completado=False
    )

    msg = intentar_iniciar_formulario_al_completar_modulo(estudiante, progreso, m4, m5)

    assert msg and "Pregunta específica Nitrofert" in msg
    sesion = SesionFormulario.objects.get(estudiante=estudiante, completado=False)
    assert sesion.formulario.cliente_id == cliente_a.id
    # Aseguro que el cliente B no se vio afectado
    assert not SesionFormulario.objects.filter(estudiante__cliente=cliente_b).exists()


def test_filtro_cliente_global_aplica_si_no_hay_especifico():
    """Si no existe TF específico del cliente, se usa el TF global (cliente=None)."""
    cliente = ClienteFactory()
    cur, m4, m5 = _bootstrap_curso_modulos()
    _crear_tf_con_paso(
        nombre="GEI Global", curso=cur, modulo=m4, cliente=None, pregunta="Pregunta global única.",
    )

    estudiante = EstudianteFactory(cliente=cliente)
    progreso = ProgresoEstudiante.objects.create(
        estudiante=estudiante, curso=cur, modulo_actual=m4, completado=False
    )

    msg = intentar_iniciar_formulario_al_completar_modulo(estudiante, progreso, m4, m5)

    assert msg and "Pregunta global única" in msg
    sesion = SesionFormulario.objects.get(estudiante=estudiante, completado=False)
    assert sesion.formulario.cliente_id is None


def test_toggle_curso_off_no_dispara_formulario():
    """Aunque exista un TipoFormulario activo, si Curso.tiene_formulario_gei=False no se dispara."""
    cliente = ClienteFactory()
    cur, m4, m5 = _bootstrap_curso_modulos()
    cur.tiene_formulario_gei = False
    cur.save(update_fields=["tiene_formulario_gei"])
    _crear_tf_con_paso(
        nombre="GEI Global", curso=cur, modulo=m4, cliente=None,
        pregunta="Pregunta global única.",
    )

    estudiante = EstudianteFactory(cliente=cliente)
    progreso = ProgresoEstudiante.objects.create(
        estudiante=estudiante, curso=cur, modulo_actual=m4, completado=False
    )

    msg = intentar_iniciar_formulario_al_completar_modulo(estudiante, progreso, m4, m5)

    assert msg is None
    assert not SesionFormulario.objects.filter(estudiante=estudiante).exists()


def test_toggle_curso_on_dispara_formulario():
    """Curso.tiene_formulario_gei=True con TipoFormulario activo → SesionFormulario creada."""
    cliente = ClienteFactory()
    cur, m4, m5 = _bootstrap_curso_modulos()
    assert cur.tiene_formulario_gei is True  # default del factory
    _crear_tf_con_paso(
        nombre="GEI Global", curso=cur, modulo=m4, cliente=None,
        pregunta="Pregunta global única.",
    )

    estudiante = EstudianteFactory(cliente=cliente)
    progreso = ProgresoEstudiante.objects.create(
        estudiante=estudiante, curso=cur, modulo_actual=m4, completado=False
    )

    msg = intentar_iniciar_formulario_al_completar_modulo(estudiante, progreso, m4, m5)

    assert msg is not None
    assert SesionFormulario.objects.filter(estudiante=estudiante, completado=False).exists()


def test_cliente_diferente_no_dispara():
    """Si solo existe un TF para Cliente A, un estudiante de Cliente B NO debe disparar formulario."""
    cliente_a = ClienteFactory(nombre="Nitrofert")
    cliente_b = ClienteFactory(nombre="TechnoServe")
    cur, m4, m5 = _bootstrap_curso_modulos()
    _crear_tf_con_paso(
        nombre="GEI solo A", curso=cur, modulo=m4, cliente=cliente_a,
        pregunta="Pregunta solo A.",
    )

    estudiante_b = EstudianteFactory(cliente=cliente_b)
    progreso = ProgresoEstudiante.objects.create(
        estudiante=estudiante_b, curso=cur, modulo_actual=m4, completado=False
    )

    msg = intentar_iniciar_formulario_al_completar_modulo(estudiante_b, progreso, m4, m5)

    assert msg is None
    assert not SesionFormulario.objects.filter(estudiante=estudiante_b).exists()


def test_calcular_balance_gei_emisiones_basicas():
    e = EstudianteFactory()
    c = CursoFactory()
    f = FichaGEI.objects.create(
        estudiante=e,
        curso=c,
        fertilizante_kg=100.0,
        concentracion_n_pct=46.0,
        tipo_combustible="diesel",
        combustible_gal=10.0,
        energia_kwh=500.0,
        residuos_ton=2.0,
        manejo_residuos="compost",
        produccion_kg=1000.0,
        tiene_bosque=False,
    )
    r = calcular_balance_gei(f)
    assert r["emisiones"]["total_kg_co2e"] > 0
    assert r["balance_neto_tco2e"] is not None
    assert r["intensidad_kg_co2e_por_kg"] is not None
    assert r["comparacion_benchmark"]["evaluacion"] in ("excelente", "bueno", "mejorable")


def test_persistir_resultado_gei_crea_registro():
    e = EstudianteFactory()
    c = CursoFactory()
    f = FichaGEI.objects.create(
        estudiante=e,
        curso=c,
        fertilizante_kg=50.0,
        concentracion_n_pct=20.0,
        combustible_gal=5.0,
        tipo_combustible="gasolina",
        energia_kwh=100.0,
        residuos_ton=1.0,
        manejo_residuos="externo",
        produccion_kg=500.0,
        tiene_bosque=False,
    )
    persistir_resultado_gei(f)
    obj = ResultadoGEI.objects.get(ficha=f)
    assert obj.em_total_kg is not None
    assert obj.completitud_calculo_pct == 100


def test_generar_mensaje_whatsapp_incluye_balance():
    e = EstudianteFactory()
    c = CursoFactory()
    f = FichaGEI.objects.create(
        estudiante=e,
        curso=c,
        fertilizante_kg=10.0,
        concentracion_n_pct=15.0,
        combustible_gal=2.0,
        tipo_combustible="diesel",
        energia_kwh=50.0,
        residuos_ton=0.5,
        manejo_residuos="compost",
        produccion_kg=200.0,
        tiene_bosque=False,
    )
    persistir_resultado_gei(f)
    msg = generar_mensaje_resultado_whatsapp(f)
    assert "Balance GEI" in msg
    assert "tCO" in msg
    assert "módulo 6" in msg.lower() or "modulo 6" in msg.lower()


@mock.patch("core.utils.enviar_whatsapp_twilio")
def test_modulo5_dispara_whatsapp_si_gei_activo(mock_send):
    cliente = ClienteFactory()
    cur, _m4, m5 = _bootstrap_curso_modulos()
    cur.tiene_formulario_gei = True
    cur.save(update_fields=["tiene_formulario_gei"])
    est = EstudianteFactory(cliente=cliente, telefono="573001112233")
    FichaGEI.objects.create(
        estudiante=est,
        curso=cur,
        cliente=cliente,
        fertilizante_kg=20.0,
        concentracion_n_pct=30.0,
        combustible_gal=1.0,
        tipo_combustible="diesel",
        energia_kwh=80.0,
        residuos_ton=0.2,
        manejo_residuos="compost",
        produccion_kg=300.0,
        tiene_bosque=False,
    )
    progreso = ProgresoEstudiante.objects.create(estudiante=est, curso=cur, modulo_actual=m5, completado=False)
    ModuloCompletado.objects.create(progreso=progreso, modulo=m5)
    mock_send.assert_called_once()
    body = mock_send.call_args[0][1]
    assert "Balance GEI" in body


@mock.patch("core.utils.enviar_whatsapp_twilio")
def test_modulo5_no_whatsapp_si_curso_sin_gei(mock_send):
    cliente = ClienteFactory()
    cur, _m4, m5 = _bootstrap_curso_modulos()
    cur.tiene_formulario_gei = False
    cur.save(update_fields=["tiene_formulario_gei"])
    est = EstudianteFactory(cliente=cliente)
    FichaGEI.objects.create(estudiante=est, curso=cur, cliente=cliente, fertilizante_kg=1.0, concentracion_n_pct=10.0)
    progreso = ProgresoEstudiante.objects.create(estudiante=est, curso=cur, modulo_actual=m5, completado=False)
    ModuloCompletado.objects.create(progreso=progreso, modulo=m5)
    mock_send.assert_not_called()
