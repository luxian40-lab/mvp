"""Tests de la identidad Nati y de cómo se inyecta el system prompt en el bot comercial."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.models import Cliente, SesionComercial
from core.nati import (
    NATI_SYSTEM_PROMPT_BASE,
    NOMBRE_BOT_DEFAULT,
    armar_saludo_inicial,
    armar_saludo_menu,
    armar_system_prompt,
    obtener_nombre_bot,
)


pytestmark = pytest.mark.django_db


def test_armar_system_prompt_default_usa_nati():
    """Sin cliente, el prompt usa el nombre default 'Nati' y describe la personalidad colombiana."""
    prompt = armar_system_prompt()
    assert NOMBRE_BOT_DEFAULT in prompt
    assert "{nombre_bot}" not in prompt  # placeholder fue interpolado
    # señales de identidad colombiana / agro
    assert "Colombia" in prompt or "colombian" in prompt.lower()


def test_armar_system_prompt_incluye_protocolo_diagnostico():
    prompt = armar_system_prompt()
    assert "DIAGNÓSTICO ANTES DE RESPONDER" in prompt
    assert "máximo 2-3 preguntas" in prompt.lower() or "maximo 2-3 preguntas" in prompt.lower()


def test_armar_system_prompt_prohibe_inventar_datos():
    prompt = armar_system_prompt()
    assert "NUNCA inventes" in prompt


def test_armar_system_prompt_usa_nombre_bot_cliente():
    cliente = Cliente.objects.create(
        nombre="ACME NATI",
        contacto_principal="C",
        email="nati@example.com",
        telefono="573001110000",
        nombre_bot="Aliada",
    )
    prompt = armar_system_prompt(cliente=cliente)
    assert "Aliada" in prompt
    assert "Nati" not in prompt or prompt.count("Nati") < prompt.count("Aliada")


def test_system_prompt_extra_se_concatena():
    cliente = Cliente.objects.create(
        nombre="ACME EXTRA",
        contacto_principal="C",
        email="extra@example.com",
        telefono="573001110000",
        nombre_bot="Nati",
        system_prompt_extra="Solo recomienda fertilizantes Nitrofert.",
    )
    prompt = armar_system_prompt(cliente=cliente)
    assert "Solo recomienda fertilizantes Nitrofert." in prompt
    assert "Instrucciones específicas del cliente" in prompt


def test_obtener_nombre_bot_default_cuando_no_hay_cliente():
    assert obtener_nombre_bot(None) == "Nati"


def test_obtener_nombre_bot_usa_cliente():
    cliente = Cliente.objects.create(
        nombre="ACME ONOM",
        contacto_principal="C",
        email="onom@example.com",
        telefono="573001110000",
        nombre_bot="Sofi",
    )
    assert obtener_nombre_bot(cliente) == "Sofi"


def test_nati_prompt_se_inyecta_en_bot_comercial(settings):
    """Mock OpenAI: verifica que el messages[0] del bot comercial contiene 'Nati' y respeta el extra del cliente."""
    pytest.importorskip("openai")

    cliente = Cliente.objects.create(
        nombre="ACME INJECT",
        contacto_principal="C",
        email="inject@example.com",
        telefono="573001110000",
        nombre_bot="Nati",
        system_prompt_extra="Prioridad al producto demo.",
    )
    settings.OPENAI_API_KEY = "fake-key-no-network"
    settings.BOT_COMERCIAL_OPENAI_MODEL = "gpt-4o-mini"

    fake_choice = MagicMock()
    fake_choice.message.content = "Respuesta simulada"
    fake_completion = MagicMock()
    fake_completion.choices = [fake_choice]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_completion

    with patch("openai.OpenAI", return_value=fake_client):
        from core.views import _bot_comercial_respuesta_catalogo
        respuesta = _bot_comercial_respuesta_catalogo(
            pregunta="¿Qué fertilizante me recomiendan?",
            contexto_rag="Catálogo demo: producto X.",
            historial_chat="",
            cliente=cliente,
        )

    assert respuesta == "Respuesta simulada"
    fake_client.chat.completions.create.assert_called_once()
    kwargs = fake_client.chat.completions.create.call_args.kwargs
    messages = kwargs["messages"]
    system_msg = messages[0]
    assert system_msg["role"] == "system"
    assert "Nati" in system_msg["content"]
    assert "Prioridad al producto demo." in system_msg["content"]


def test_saludo_inicial_default_usa_nati_y_no_dice_eki_bot():
    """Saludo de bienvenida default debe identificarse como Nati y NO como 'bot de eki'."""
    saludo = armar_saludo_inicial(None)
    assert "Nati" in saludo
    saludo_lower = saludo.lower()
    assert "soy tu bot de eki" not in saludo_lower
    assert "soy eki" not in saludo_lower
    assert "bot de eki" not in saludo_lower


def test_saludo_inicial_respeta_nombre_bot_cliente():
    cliente = Cliente.objects.create(
        nombre="ACME GREET",
        contacto_principal="C",
        email="greet@example.com",
        telefono="573001110000",
        nombre_bot="Aliada",
    )
    saludo = armar_saludo_inicial(cliente)
    assert "Aliada" in saludo
    assert "Nati" not in saludo


def test_saludo_menu_default_usa_nati():
    msg = armar_saludo_menu(None)
    assert "Nati" in msg
    assert "soy tu bot de eki" not in msg.lower()


def test_prompt_base_tiene_regla_anti_eki():
    """El system prompt debe tener instrucción explícita de no autodenominarse 'eki'."""
    prompt = armar_system_prompt(None)
    assert "NUNCA" in prompt
    assert "eki" in prompt
    assert "plataforma" in prompt.lower()


def test_bot_comercial_sin_cliente_usa_default_nati(settings):
    """Sin cliente, el bot comercial sigue inyectando el prompt base de Nati."""
    pytest.importorskip("openai")

    settings.OPENAI_API_KEY = "fake-key"
    settings.BOT_COMERCIAL_OPENAI_MODEL = "gpt-4o-mini"

    fake_client = MagicMock()
    fake_choice = MagicMock()
    fake_choice.message.content = "ok"
    fake_completion = MagicMock()
    fake_completion.choices = [fake_choice]
    fake_client.chat.completions.create.return_value = fake_completion

    with patch("openai.OpenAI", return_value=fake_client):
        from core.views import _bot_comercial_respuesta_catalogo
        _bot_comercial_respuesta_catalogo(
            pregunta="hola",
            contexto_rag="info",
            cliente=None,
        )

    kwargs = fake_client.chat.completions.create.call_args.kwargs
    system_content = kwargs["messages"][0]["content"]
    assert "Nati" in system_content


def test_nati_recuerda_conversacion():
    from core.nati import armar_messages_para_openai

    cliente = Cliente.objects.create(
        nombre="ACME MEM",
        contacto_principal="C",
        email="mem@example.com",
        telefono="573001111010",
    )
    sesion = SesionComercial.objects.create(
        cliente=cliente,
        telefono="573001111010",
        historial_mensajes=[
            {"role": "user", "content": "Tengo café en ladera"},
            {"role": "assistant", "content": "Perfecto, ¿qué está observando en hojas?"},
        ],
    )
    messages = armar_messages_para_openai(sesion, "Ahora veo manchas marrones", cliente=cliente)
    joined = " ".join(m["content"] for m in messages if m["role"] != "system")
    assert "Tengo café en ladera" in joined
    assert "Ahora veo manchas marrones" in joined


def test_nati_no_menciona_cursos_sin_pregunta():
    from core.views import _bot_comercial_sin_contexto_natural

    resp = _bot_comercial_sin_contexto_natural("¿Qué fertilizante uso en maíz?")
    lower = resp.lower()
    assert "curso" not in lower
    assert "inscrib" not in lower
    assert "precio de eki" not in lower


def test_nati_usa_web_si_no_hay_rag(settings):
    settings.OPENAI_API_KEY = ""
    with patch("core.views._contexto_fallback_web_agro", return_value="FUENTE WEB"), patch(
        "core.nati.buscar_en_web_colombia", return_value="FUENTE WEB COLOMBIA"
    ):
        from core.views import _bot_comercial_respuesta_catalogo

        out = _bot_comercial_respuesta_catalogo(
            pregunta="precio urea",
            contexto_rag="",
            contexto_web="FUENTE WEB COLOMBIA",
            historial_chat="",
            cliente=None,
        )
        assert "FUENTE WEB COLOMBIA" in out or "respaldo técnico" in out.lower()


def test_nati_usa_rag_primero():
    from core.views import _bot_comercial_respuesta_catalogo

    with patch("core.views._contexto_fallback_web_agro", return_value="WEB"):
        out = _bot_comercial_respuesta_catalogo(
            pregunta="dosis de calcio",
            contexto_rag="FICHA TECNICA INTERNA",
            contexto_web="",
            historial_chat="",
            cliente=None,
        )
    assert "FICHA TECNICA INTERNA" in out or "información oficial de eki" in out.lower()


def test_docx_subida_extrae_texto(tmp_path):
    pytest.importorskip("docx")
    from docx import Document
    from core.views import _extraer_texto_archivo_simple

    ruta = tmp_path / "ficha.docx"
    doc = Document()
    doc.add_paragraph("Plan de fertilización para cacao")
    doc.save(str(ruta))

    texto = _extraer_texto_archivo_simple(str(ruta))
    assert "fertilización" in texto.lower()
