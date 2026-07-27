"""
Prueba: mancha en tomate → anamnesis → ¿recomienda producto?

  python manage.py shell -c "exec(open('scripts/smoke_nat_mancha_tomate.py', encoding='utf-8').read())"
"""
from __future__ import annotations

from unittest.mock import patch

from django.db import transaction
from django.test import override_settings
from django.utils import timezone

from core.contexto_agro import actualizar_contexto_desde_mensaje, obtener_o_crear_contexto
from core.models import Cliente, ProductoCatalogo, SesionComercial
from core.nat_diagnostico import es_consulta_diagnostico, siguiente_pregunta_diagnostico
from core.nati import armar_system_prompt, obtener_contexto_productos


def _ok(msg: str) -> None:
    print(f'  OK  {msg}')


def _info(msg: str) -> None:
    print(f'  ..  {msg}')


def _fail(msg: str) -> None:
    print(f' FAIL {msg}')
    raise SystemExit(1)


def _caminar_anamnesis(sesion, ctx) -> list[tuple[str, str | None]]:
    """Simula productor respondiendo hasta que Nat suelta el LLM/catálogo."""
    dialogo: list[tuple[str, str | None]] = []
    turnos = [
        'tengo mancha en el tomate',
        'Boyaca Guateque',
        'manchas marrones en hojas de abajo',
        'como media parcela, hojas bajas',
        'hace 5 dias y va empeorando',
        'floracion',
        'solo riego, no he fumigado',
        'sin foto',
    ]
    for msg in turnos:
        actualizar_contexto_desde_mensaje(sesion, msg)
        ctx.refresh_from_db()
        pregunta = siguiente_pregunta_diagnostico(ctx, msg)
        dialogo.append((msg, pregunta))
        _info(f'U: {msg[:60]}')
        if pregunta:
            _info(f'Nati: {pregunta[:110]}')
        else:
            _info('Nati: (fin anamnesis → pasa a recomendación con catálogo/LLM)')
            break
    return dialogo


def run() -> None:
    print('=== Prueba Nat: mancha en tomate + producto ===')
    stamp = timezone.now().strftime('%H%M%S')

    if not es_consulta_diagnostico('tengo mancha en el tomate'):
        _fail('no detecta "mancha" como consulta de diagnóstico')
    _ok('detecta síntoma "mancha"')

    from core.contexto_agro import extraer_campos_desde_mensaje
    campos0 = extraer_campos_desde_mensaje('tengo mancha en el tomate')
    if 'tomate' not in (campos0.get('cultivo') or '').lower():
        _fail(f'no extrajo cultivo tomate: {campos0}')
    if 'mancha' not in (campos0.get('problema') or '').lower():
        _fail(f'no extrajo problema mancha: {campos0}')
    _ok(f'extrae cultivo={campos0.get("cultivo")!r} problema={campos0.get("problema")!r}')

    with transaction.atomic():
        # --- Caso A: org SIN producto ---
        org_vacia = Cliente.objects.create(
            nombre=f'Smoke Nat Sin Cat {stamp}',
            contacto_principal='Smoke',
            email=f'smoke-nat-vacio-{stamp}@test.local',
            telefono=f'57310{stamp}'[-12:],
            activo=True,
            tipo_proyecto='nat',
            portal_productos='nat',
            numero_whatsapp_nat='whatsapp:+15550008881',
        )
        prompt_vacio = armar_system_prompt(cliente=org_vacia)
        if obtener_contexto_productos(org_vacia).strip():
            _fail('org vacía no debería tener catálogo')
        if 'PLAN B' not in prompt_vacio:
            _fail('sin catálogo debería activar PLAN B (manejo + web/fórmula)')
        _ok('SIN catálogo: Plan B (orienta con manejo/principio activo, no inventa marca)')

        # --- Caso B: org CON fungicida mancha/tomate ---
        org = Cliente.objects.create(
            nombre=f'Smoke Nat Mancha Tomate {stamp}',
            contacto_principal='Smoke',
            email=f'smoke-nat-mancha-{stamp}@test.local',
            telefono=f'57311{stamp}'[-12:],
            activo=True,
            tipo_proyecto='nat',
            portal_productos='nat',
            numero_whatsapp_nat='whatsapp:+15550008882',
        )
        prod = ProductoCatalogo.objects.create(
            cliente=org,
            nombre='Fungicida Tomate Mancha Foliar',
            sku=f'TOM-MANCHA-{stamp}',
            descripcion='Control de manchas foliares y hongos en tomate',
            problema_que_resuelve='manchas en hoja, tizón, hongos foliar en tomate',
            categoria='fungicida',
            cultivos_objetivo='tomate',
            dosis='2-3 cc/L según etiqueta',
            precio_cop=52000,
            unidad='250 ml',
            activo=True,
            url_producto='https://ejemplo.eki.local/fungicida-tomate',
        )
        ctx_cat = obtener_contexto_productos(org)
        prompt = armar_system_prompt(cliente=org)
        if prod.nombre not in ctx_cat or prod.nombre not in prompt:
            _fail('producto no inyectado en prompt')
        if 'CÓMO RECOMENDAR PRODUCTOS' not in prompt:
            _fail('faltan reglas de recomendación')
        _ok(f'CON catálogo: "{prod.nombre}" entra al prompt (cultivo=tomate, problema=manchas)')

        sesion = SesionComercial.objects.create(
            telefono=f'57312{stamp}'[-12:],
            cliente=org,
        )
        ctx = obtener_o_crear_contexto(sesion)
        print('\n--- Diálogo anamnesis (mancha tomate) ---')
        dialogo = _caminar_anamnesis(sesion, ctx)
        ctx.refresh_from_db()
        if 'tomate' not in (ctx.cultivo or '').lower():
            _fail(f'cultivo final={ctx.cultivo!r}')
        if 'mancha' not in (ctx.problema or '').lower():
            _fail(f'problema final={ctx.problema!r}')
        if dialogo[-1][1] is not None:
            _fail(f'anamnesis no terminó: {dialogo[-1][1]!r}')
        _ok('anamnesis completa → listo para recomendación')

        respuesta_llm = (
            'Entendido: manchas foliares en tomate en Guateque.\n\n'
            'Priorice aireación y evite mojar el follaje al regar.\n\n'
            f'📦 {prod.nombre}\n'
            f'SKU: {prod.sku}\n'
            'Sirve para: manchas en hoja / hongos foliar en tomate\n'
            'Dosis: 2-3 cc/L según etiqueta\n'
            'Precio: $52.000 COP por 250 ml\n'
            f'Comprar acá: {prod.url_producto}\n'
            'Verifique el precio final en el punto de venta.'
        )
        with override_settings(
            OPENAI_API_KEY='sk-test',
            TWILIO_ACCOUNT_SID='ACtest',
            TWILIO_AUTH_TOKEN='tok',
            TWILIO_PHONE_NUMBER='whatsapp:+15550008882',
            BOT_COMERCIAL_WHATSAPP_NUMBER='whatsapp:+15550008882',
            BOT_COMERCIAL_FORCE_ROUTING=True,
            SECURE_SSL_REDIRECT=False,
        ):
            from core.bot_comercial import webhook as wh
            from core.nat_router import NatRoutingDecision

            fake_routing = NatRoutingDecision(
                modo='catalogo',
                modelo='gpt-4o-mini',
                razon='smoke-mancha',
                usar_web=False,
                escala_premium=False,
            )
            with patch('core.nat_diagnostico.siguiente_pregunta_diagnostico', return_value=None):
                with patch.object(wh, '_bot_comercial_respuesta_catalogo', return_value=respuesta_llm):
                    with patch('core.nat_router.decidir_routing_nat', return_value=fake_routing):
                        with patch.object(
                            wh, 'enviar_whatsapp_twilio',
                            return_value={'success': True, 'mensaje_id': 'SMmancha'},
                        ) as mock_txt:
                            wh._procesar_bot_comercial_twilio_webhook({
                                'From': f'whatsapp:57312{stamp}'[-20:],
                                'To': 'whatsapp:+15550008882',
                                'Body': 'ya le conté: mancha en tomate, ¿qué producto me sirve?',
                                'MessageSid': f'SMmancha{stamp}',
                                'NumMedia': '0',
                            })
                            if not mock_txt.called:
                                _fail('webhook no envió respuesta')
                            call_str = str(mock_txt.call_args)
                            if prod.nombre not in call_str and 'Fungicida Tomate' not in call_str:
                                _fail(f'respuesta sin producto: {mock_txt.call_args!r}')
                            _ok('webhook recomienda el fungicida del catálogo (📦 nombre + dosis + precio)')

        print('\n=== Resumen ===')
        print('1) "mancha en tomate" SÍ dispara diagnóstico (pregunta por pregunta).')
        print('2) SIN producto en catálogo de la org → NO inventa producto.')
        print(f'3) CON ficha "{prod.nombre}" → SÍ recomienda ese producto.')
        print('4) La recomendación sale del ProductoCatalogo de esa org WhatsApp (no inventa marcas).')
        transaction.set_rollback(True)
        print('=== PASS (rollback) ===')


run()
