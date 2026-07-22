"""Tests Nat: foto de cultivo (visión) y foto de producto por WhatsApp."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from core.bot_comercial.productos_media import (
    extraer_claves_productos_respuesta,
    fotos_productos_para_whatsapp,
)
from core.bot_comercial.vision import (
    _PROMPT_VISION,
    diagnosticar_imagen_cultivo,
    url_vision_desde_twilio,
)
from core.models import Cliente, ProductoCatalogo


pytestmark = pytest.mark.django_db


def test_prompt_vision_pide_hipotesis_no_veredicto():
    assert 'POSIBLES causas' in _PROMPT_VISION
    assert 'certeza' in _PROMPT_VISION.lower() or 'Nunca afirme' in _PROMPT_VISION
    assert 'productor' in _PROMPT_VISION.lower()
    assert 'Empiece SIEMPRE' in _PROMPT_VISION


def test_es_analisis_vision_util_filtra_errores():
    from core.bot_comercial.vision import es_analisis_vision_util

    assert not es_analisis_vision_util('Recibí su foto. El análisis visual no está disponible.')
    assert not es_analisis_vision_util('corto')
    assert es_analisis_vision_util(
        '*Lo que se observa:* orificios\n*Posibles causas:*\n1) larva\n2) pudrición'
    )


def test_url_producto_relativa_sin_base_no_se_envia(settings):
    settings.APP_PUBLIC_URL = ''
    settings.MEDIA_HOST = ''
    settings.MEDIA_URL = '/media/'
    org = Cliente.objects.create(
        nombre='Org Rel',
        contacto_principal='A',
        email='rel@test.com',
        telefono='573001000001',
        activo=True,
        tipo_proyecto='nat',
    )
    img = SimpleUploadedFile('r.jpg', b'\xff\xd8\xff\xd9', content_type='image/jpeg')
    ProductoCatalogo.objects.create(
        cliente=org,
        nombre='Prod Rel',
        sku='REL-1',
        descripcion='d',
        problema_que_resuelve='p',
        activo=True,
        imagen=img,
    )
    fotos = fotos_productos_para_whatsapp(
        org, '📦 Prod Rel\nSKU: REL-1\n', limite=2,
    )
    # Sin base pública absoluta no debe devolver URL relativa
    assert fotos == [] or all(
        (f.get('url') or '').startswith('https://') for f in fotos
    )


@override_settings(TWILIO_ACCOUNT_SID='ACtest', TWILIO_AUTH_TOKEN='tok')
@patch('requests.get')
def test_url_vision_descarga_twilio_con_auth(mock_get):
    mock_get.return_value = MagicMock(
        content=b'\xff\xd8\xfffakejpeg',
        headers={'Content-Type': 'image/jpeg'},
        raise_for_status=MagicMock(),
    )
    url = url_vision_desde_twilio(
        'https://api.twilio.com/media/ME123',
        'image/jpeg',
    )
    assert url.startswith('data:image/jpeg;base64,')
    mock_get.assert_called_once()
    assert mock_get.call_args.kwargs.get('auth') == ('ACtest', 'tok')


@override_settings(OPENAI_API_KEY='sk-test')
@patch('core.ai_capabilities.resolver_ai_capability', return_value=True)
@patch('core.bot_comercial.vision.url_vision_desde_twilio', return_value='data:image/jpeg;base64,abc')
@patch('openai.OpenAI')
def test_diagnosticar_imagen_usa_prompt_hipotesis(mock_openai, _url, _cap):
    choice = MagicMock()
    choice.message.content = (
        '*Lo que se observa:* manchas en hoja\n'
        '*Posibles causas:*\n1) hongo foliar\n2) deficiencia\n'
        '*Qué conviene verificar en finca:* humedad\n'
        '*Importante:* usted decide'
    )
    mock_openai.return_value.chat.completions.create.return_value = MagicMock(
        choices=[choice],
    )
    out = diagnosticar_imagen_cultivo(
        'https://api.twilio.com/media/ME1',
        'image/jpeg',
        cliente=None,
    )
    assert 'Posibles causas' in out or 'posibles' in out.lower()
    kwargs = mock_openai.return_value.chat.completions.create.call_args.kwargs
    system = kwargs['messages'][0]['content']
    assert 'POSIBLES causas' in system
    assert 'Nunca afirme' in system or 'certeza' in system.lower()


def test_extraer_sku_y_nombre_de_respuesta():
    texto = (
        "Le oriento así.\n\n"
        "📦 Fungicida Café Plus\n"
        "SKU: FUNG-CAFE-500\n"
        "Dosis: 300g\n"
    )
    skus, nombres = extraer_claves_productos_respuesta(texto)
    assert skus == ['FUNG-CAFE-500']
    assert nombres == ['Fungicida Café Plus']


def test_extraer_sku_flexible_sin_emoji():
    texto = (
        "Le recomiendo: Bioestimulante Verde\n"
        "sku BIO-99\n"
        "Dosis según etiqueta."
    )
    skus, nombres = extraer_claves_productos_respuesta(texto)
    assert 'BIO-99' in skus
    assert any('Bioestimulante' in n for n in nombres)


def test_match_producto_por_nombre_en_texto_sin_formato():
    """Sin 📦 ni SKU: si el nombre del catálogo aparece en el texto, manda foto."""
    org = Cliente.objects.create(
        nombre='Org Soft Match',
        contacto_principal='A',
        email='soft@test.com',
        telefono='573001234570',
        activo=True,
        tipo_proyecto='nat',
    )
    img = SimpleUploadedFile('s.jpg', b'\xff\xd8\xff\xd9', content_type='image/jpeg')
    ProductoCatalogo.objects.create(
        cliente=org,
        nombre='Control Fruto Tomate Plus',
        sku='TOM-X',
        descripcion='d',
        problema_que_resuelve='orificios',
        activo=True,
        imagen=img,
    )
    texto = (
        "Puede usar Control Fruto Tomate Plus en dosis de etiqueta. "
        "Verifique el precio final en el punto de venta."
    )
    with override_settings(APP_PUBLIC_URL='https://app.eki.technology'):
        fotos = fotos_productos_para_whatsapp(org, texto, limite=2)
    assert len(fotos) == 1
    assert fotos[0]['nombre'] == 'Control Fruto Tomate Plus'


@override_settings(OPENAI_API_KEY='sk-test')
@patch('core.ai_capabilities.resolver_ai_capability', return_value=False)
@patch('core.bot_comercial.vision.url_vision_desde_twilio', return_value='data:image/jpeg;base64,abc')
@patch('openai.OpenAI')
def test_vision_sigue_con_capability_off(mock_openai, _url, _cap):
    choice = MagicMock()
    choice.message.content = (
        '*Lo que se observa:* manchas\n'
        '*Posibles causas:*\n1) hongo\n'
        '*Importante:* usted decide'
    )
    mock_openai.return_value.chat.completions.create.return_value = MagicMock(
        choices=[choice],
    )
    out = diagnosticar_imagen_cultivo(
        'https://api.twilio.com/media/ME1',
        'image/jpeg',
        cliente=None,
    )
    assert 'Posibles causas' in out or 'posibles' in out.lower()
    mock_openai.assert_called_once()


def test_fotos_productos_match_por_sku():
    org = Cliente.objects.create(
        nombre='Org Foto Nat',
        contacto_principal='A',
        email='foto-nat@test.com',
        telefono='573001234567',
        activo=True,
        tipo_proyecto='nat',
    )
    img = SimpleUploadedFile('prod.jpg', b'\xff\xd8\xff\xd9', content_type='image/jpeg')
    ProductoCatalogo.objects.create(
        cliente=org,
        nombre='Fungicida Café Plus',
        sku='FUNG-CAFE-500',
        descripcion='Control foliar',
        problema_que_resuelve='Roya y manchas',
        activo=True,
        imagen=img,
    )
    ProductoCatalogo.objects.create(
        cliente=org,
        nombre='Sin foto',
        sku='SIN-FOTO',
        descripcion='x',
        problema_que_resuelve='y',
        activo=True,
    )
    texto = "📦 Fungicida Café Plus\nSKU: FUNG-CAFE-500\n"
    with override_settings(APP_PUBLIC_URL='https://app.eki.technology'):
        fotos = fotos_productos_para_whatsapp(org, texto, limite=2)
    assert len(fotos) == 1
    assert fotos[0]['nombre'] == 'Fungicida Café Plus'
    assert fotos[0]['url'].startswith('https://')


@patch('core.bot_comercial.productos_media.enviar_whatsapp_twilio')
def test_enviar_fotos_productos_llama_twilio_con_media(mock_send):
    from core.bot_comercial.productos_media import enviar_fotos_productos_whatsapp

    mock_send.return_value = {'success': True, 'mensaje_id': 'SM1'}
    productos = [{'nombre': 'Prod A', 'url': 'https://cdn.example.com/a.jpg', 'sku': 'A'}]
    res = enviar_fotos_productos_whatsapp('573001111111', productos, from_number='whatsapp:+1555')
    assert len(res) == 1
    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs.get('media_url') == 'https://cdn.example.com/a.jpg'
    assert mock_send.call_args.args[1].startswith('📦')


@override_settings(
    OPENAI_API_KEY='sk-test',
    TWILIO_ACCOUNT_SID='ACtest',
    TWILIO_AUTH_TOKEN='tok',
    TWILIO_PHONE_NUMBER='whatsapp:+15550001111',
    BOT_COMERCIAL_WHATSAPP_NUMBER='whatsapp:+15550001111',
    BOT_COMERCIAL_FORCE_ROUTING=True,
    SECURE_SSL_REDIRECT=False,
    APP_PUBLIC_URL='https://app.eki.technology',
)
@patch('core.bot_comercial.productos_media.enviar_whatsapp_twilio')
@patch('core.bot_comercial.webhook.enviar_whatsapp_twilio')
@patch('core.nat_diagnostico.siguiente_pregunta_diagnostico', return_value=None)
@patch('core.bot_comercial.webhook._bot_comercial_diagnosticar_imagen')
@patch('core.bot_comercial.webhook._bot_comercial_respuesta_catalogo')
def test_webhook_foto_entrada_y_foto_producto(
    mock_catalogo,
    mock_vision,
    _diag,
    mock_send_wh,
    mock_send_foto,
):
    """Cubre: foto entrada (visión) + foto producto al recomendar."""
    from core.bot_comercial import webhook as wh
    from core.nat_router import NatRoutingDecision

    fake_routing = NatRoutingDecision(
        modo='catalogo',
        modelo='gpt-4o-mini',
        razon='test',
        usar_web=False,
        escala_premium=False,
        rag_max_similitud=None,
    )

    org = Cliente.objects.create(
        nombre='Org WA Nat',
        contacto_principal='A',
        email='wa-nat@test.com',
        telefono='573009998877',
        activo=True,
        tipo_proyecto='nat',
        numero_whatsapp_nat='whatsapp:+15550001111',
    )
    img = SimpleUploadedFile('p.jpg', b'\xff\xd8\xff\xd9', content_type='image/jpeg')
    ProductoCatalogo.objects.create(
        cliente=org,
        nombre='Bioestimulante Verde',
        sku='BIO-1',
        descripcion='d',
        problema_que_resuelve='estres',
        activo=True,
        imagen=img,
    )

    mock_vision.return_value = (
        '*Lo que se observa:* hojas pálidas\n'
        '*Posibles causas:*\n1) falta de N\n'
        '*Importante:* usted decide'
    )
    mock_catalogo.return_value = (
        "Orientación.\n\n"
        "📦 Bioestimulante Verde\n"
        "SKU: BIO-1\n"
        "Verifique el precio final en el punto de venta."
    )
    mock_send_wh.return_value = {'success': True, 'mensaje_id': 'SMx'}
    mock_send_foto.return_value = {'success': True, 'mensaje_id': 'SMfoto'}

    with patch('core.nat_router.decidir_routing_nat', return_value=fake_routing):
        with patch.object(wh, '_bot_comercial_respuesta_catalogo', mock_catalogo):
            wh._procesar_bot_comercial_twilio_webhook({
                'From': 'whatsapp:573001112233',
                'To': 'whatsapp:+15550001111',
                'Body': 'café con hojas amarillas',
                'MessageSid': 'SMfoto001',
                'NumMedia': '1',
                'MediaContentType0': 'image/jpeg',
                'MediaUrl0': 'https://api.twilio.com/media/MEx',
            })

    mock_vision.assert_called_once()
    mock_catalogo.assert_called_once()
    mock_send_wh.assert_called_once()
    assert mock_send_foto.call_count >= 1
    assert mock_send_foto.call_args.kwargs.get('media_url')
