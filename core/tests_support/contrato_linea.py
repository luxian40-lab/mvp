"""Arnés de contratos de línea (fase A1 de PLAN_MODULARIDAD_EKI.md).

Un contrato escribe a una línea como lo haría Meta y mira lo que sale.
Nada llega a la red: lo que va por `requests` (Graph y Twilio) queda
capturado con una respuesta falsa; cualquier otro host falla, y `httpx`
(OpenAI, ElevenLabs) también, salvo `chat/completions` cuando el contrato
fija un texto con `salida.llm_responde`. El reloj está fijo y las pausas de
`time.sleep` se anotan sin esperar.

El reloj solo cubre `django.utils.timezone.now`. Quien use
`datetime.now()` o `from django.utils.timezone import now` ve la hora real.
"""
from __future__ import annotations

import hashlib
import hmac
import itertools
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import httpx
import requests
from django.test import TestCase, override_settings
from requests.adapters import HTTPAdapter
from requests.models import Response

SECRETO_META = 'contrato-linea-secreto'
TOKEN_META = 'contrato-linea-token'
URL_WEBHOOK = '/webhook/whatsapp/'

GRAPH_HOST = 'graph.facebook.com'
TWILIO_HOST = 'api.twilio.com'
OPENAI_HOST = 'api.openai.com'
CLAVE_OPENAI_FALSA = 'sk-test-contrato-linea'

# 08:00 en Bogotá: el pico de la línea 2.
INSTANTE_BASE = datetime(2026, 10, 20, 13, 0, tzinfo=dt_timezone.utc)


@dataclass(frozen=True)
class Linea:
    phone_id: str
    e164: str
    nombre: str


LINEA_PRINCIPAL = Linea('100000000000001', '573009990001', 'Línea principal')
LINEA_2 = Linea('100000000000002', '573009990002', 'Línea 2')
WABA_PRINCIPAL = '200000000000001'
WABA_LINEA_2 = '200000000000002'

AJUSTES_LINEAS = {
    'META_LINEAS': '',
    'SANDBOX_PROVEEDOR': 'meta',
    'SANDBOX_MENU_ENABLED': True,
    'WHATSAPP_PHONE_ID': LINEA_PRINCIPAL.phone_id,
    'SANDBOX_WHATSAPP_PHONE_ID': LINEA_PRINCIPAL.phone_id,
    'BOT_COMERCIAL_SANDBOX_NUMBER': LINEA_PRINCIPAL.e164,
    'WHATSAPP_PHONE_NUMBER_ID_2': LINEA_2.phone_id,
    'WHATSAPP_NUMERO_2_E164': LINEA_2.e164,
    'WHATSAPP_BUSINESS_ACCOUNT_ID': WABA_PRINCIPAL,
    'WHATSAPP_BUSINESS_ACCOUNT_ID_2': WABA_LINEA_2,
    'EKI_CAMPANA_META_ENABLED': True,
    'META_CAMPANAS_V2_ENABLED': False,
    'WHATSAPP_TOKEN': TOKEN_META,
    'WHATSAPP_APP_SECRET': SECRETO_META,
    'WHATSAPP_REQUIRE_SIGNATURE': True,
    'WEBHOOK_CELERY_ASYNC': False,
    'SANDBOX_CELERY_ASYNC': False,
    'NAT_WEBHOOK_CELERY_ASYNC': False,
    'CELERY_TASK_ALWAYS_EAGER': True,
    'SECURE_SSL_REDIRECT': False,
    'OPENAI_API_KEY': CLAVE_OPENAI_FALSA,
}


def firmar(raw: bytes, secreto: str = SECRETO_META) -> str:
    digest = hmac.new(secreto.encode(), raw, hashlib.sha256).hexdigest()
    return f'sha256={digest}'


_wamids = itertools.count(1)


def nuevo_wamid() -> str:
    return f'wamid.contrato.{next(_wamids)}'


def payload_meta(linea: Linea, telefono: str, mensaje: dict) -> dict:
    """Un mensaje entrante tal como lo manda Cloud API a esa línea."""
    cuerpo = {'from': telefono, 'id': nuevo_wamid(), 'timestamp': '1792500000'}
    cuerpo.update(mensaje)
    return {
        'object': 'whatsapp_business_account',
        'entry': [{
            'id': 'WABA-CONTRATO',
            'changes': [{
                'field': 'messages',
                'value': {
                    'messaging_product': 'whatsapp',
                    'metadata': {
                        'display_phone_number': linea.e164,
                        'phone_number_id': linea.phone_id,
                    },
                    'contacts': [{'profile': {'name': 'Contrato'}, 'wa_id': telefono}],
                    'messages': [cuerpo],
                },
            }],
        }],
    }


def mensaje_texto(texto: str) -> dict:
    return {'type': 'text', 'text': {'body': texto}}


def mensaje_boton(id_boton: str, titulo: str = '') -> dict:
    return {
        'type': 'interactive',
        'interactive': {
            'type': 'button_reply',
            'button_reply': {'id': id_boton, 'title': titulo or id_boton},
        },
    }


def mensaje_lista(id_fila: str, titulo: str = '') -> dict:
    return {
        'type': 'interactive',
        'interactive': {
            'type': 'list_reply',
            'list_reply': {'id': id_fila, 'title': titulo or id_fila},
        },
    }


def mensaje_boton_plantilla(payload: str, texto: str = '') -> dict:
    """Botón de respuesta rápida de una plantilla (campañas)."""
    return {'type': 'button', 'button': {'payload': payload, 'text': texto or payload}}


@dataclass
class Envio:
    """Una petición que salió hacia Graph o Twilio."""

    canal: str
    metodo: str
    url: str
    phone_id: str = ''
    destino: str = ''
    tipo: str = ''
    texto: str = ''
    botones: list[str] = field(default_factory=list)
    ids: list[str] = field(default_factory=list)
    cuerpo: dict = field(default_factory=dict)

    @property
    def es_mensaje(self) -> bool:
        return self.metodo == 'POST' and self.tipo != 'reaction'


def _texto_interactivo(inter: dict) -> tuple[str, list[str], list[str]]:
    """Texto, títulos e ids de botones, filas de lista y tarjetas de carrusel."""
    texto = str((inter.get('body') or {}).get('text') or '')
    accion = inter.get('action') or {}
    pares = [
        (b.get('reply') or {})
        for b in accion.get('buttons') or []
    ]
    for seccion in accion.get('sections') or []:
        pares.extend(seccion.get('rows') or [])
    for carta in accion.get('cards') or []:
        for b in (carta.get('action') or {}).get('buttons') or []:
            pares.append(b.get('quick_reply') or b.get('reply') or {})
    botones = [str(p.get('title') or '') for p in pares if p.get('title')]
    ids = [str(p.get('id') or '') for p in pares if p.get('id')]
    return texto, botones, ids


def _envio_graph(request) -> Envio:
    partes = [p for p in urlsplit(request.url).path.split('/') if p]
    phone_id = partes[1] if len(partes) >= 3 and partes[2] == 'messages' else ''
    cuerpo: dict = {}
    if request.body:
        try:
            cuerpo = json.loads(request.body)
        except (TypeError, ValueError):
            cuerpo = {}
    tipo = str(cuerpo.get('type') or '')
    texto, botones, ids = '', [], []
    if tipo == 'text':
        texto = str((cuerpo.get('text') or {}).get('body') or '')
    elif tipo == 'interactive':
        texto, botones, ids = _texto_interactivo(cuerpo.get('interactive') or {})
    elif tipo == 'template':
        texto = str((cuerpo.get('template') or {}).get('name') or '')
    elif tipo == 'reaction':
        texto = str((cuerpo.get('reaction') or {}).get('emoji') or '')
    elif tipo:
        bloque = cuerpo.get(tipo) or {}
        texto = str(bloque.get('caption') or bloque.get('link') or '')
    return Envio(
        canal='meta',
        metodo=request.method,
        url=request.url,
        phone_id=phone_id,
        destino=str(cuerpo.get('to') or ''),
        tipo=tipo,
        texto=texto,
        botones=botones,
        ids=ids,
        cuerpo=cuerpo,
    )


def _envio_twilio(request) -> Envio:
    cuerpo_raw = request.body or ''
    if isinstance(cuerpo_raw, bytes):
        cuerpo_raw = cuerpo_raw.decode('utf-8', 'replace')
    campos = {k: v[0] for k, v in parse_qs(cuerpo_raw).items()}
    return Envio(
        canal='twilio',
        metodo=request.method,
        url=request.url,
        destino=campos.get('To', ''),
        tipo='content' if campos.get('ContentSid') else 'text',
        texto=campos.get('Body', '') or campos.get('ContentSid', ''),
        cuerpo=campos,
    )


def _respuesta(request, status: int, data: dict) -> Response:
    resp = Response()
    resp.status_code = status
    resp._content = json.dumps(data).encode()
    resp.headers['Content-Type'] = 'application/json'
    resp.encoding = 'utf-8'
    resp.url = request.url
    resp.request = request
    resp.reason = 'OK' if status < 400 else 'Error'
    return resp


class CapturaSalida:
    """Intercepta HTTPAdapter.send y la capa de transporte de httpx."""

    def __init__(self):
        self.envios: list[Envio] = []
        self.bloqueados: list[str] = []
        self.llamadas_llm: list[dict] = []
        self.texto_llm: str | None = None
        self._ids = itertools.count(1)
        self._parches = []

    def llm_responde(self, texto: str | None) -> None:
        """Con texto, chat/completions de OpenAI devuelve ese texto. None vuelve a fallar."""
        self.texto_llm = texto

    def iniciar(self) -> None:
        captura = self

        def enviar(_adapter, request, **_kwargs):
            return captura._atender(request)

        def httpx_atender(_transport, request):
            return captura._atender_httpx(request)

        self._parches = [
            patch.object(HTTPAdapter, 'send', new=enviar),
            patch.object(httpx.HTTPTransport, 'handle_request', new=httpx_atender),
        ]
        for parche in self._parches:
            parche.start()

    def detener(self) -> None:
        for parche in reversed(self._parches):
            parche.stop()
        self._parches = []

    def _atender(self, request):
        host = (urlsplit(request.url).hostname or '').lower()
        if host == GRAPH_HOST:
            envio = _envio_graph(request)
            self.envios.append(envio)
            if request.method != 'POST':
                return self._lectura_graph(request)
            if envio.tipo == 'reaction':
                return _respuesta(request, 200, {'success': True})
            return _respuesta(request, 200, {
                'messaging_product': 'whatsapp',
                'contacts': [{'input': envio.destino, 'wa_id': envio.destino}],
                'messages': [{'id': f'wamid.salida.{next(self._ids)}'}],
            })
        if host == TWILIO_HOST:
            envio = _envio_twilio(request)
            self.envios.append(envio)
            sid = f'SMcontrato{next(self._ids):022d}'
            return _respuesta(request, 201, {
                'sid': sid,
                'status': 'queued',
                'to': envio.destino,
                'from': envio.cuerpo.get('From', ''),
                'body': envio.cuerpo.get('Body', ''),
                'error_code': None,
                'error_message': None,
            })
        self.bloqueados.append(request.url)
        raise requests.ConnectionError(f'red bloqueada por el arnés de contratos: {host}')

    def _atender_httpx(self, request):
        url = str(request.url)
        es_chat = request.url.host == OPENAI_HOST and request.url.path.endswith('/chat/completions')
        if self.texto_llm is None or not es_chat:
            self.bloqueados.append(url)
            raise httpx.ConnectError('red bloqueada por el arnés de contratos', request=request)
        try:
            cuerpo = json.loads(request.read() or b'{}')
        except ValueError:
            cuerpo = {}
        self.llamadas_llm.append(cuerpo)
        return httpx.Response(200, request=request, json={
            'id': f'chatcmpl-contrato-{next(self._ids)}',
            'object': 'chat.completion',
            'created': 0,
            'model': str(cuerpo.get('model') or 'contrato'),
            'choices': [{
                'index': 0,
                'message': {'role': 'assistant', 'content': self.texto_llm},
                'finish_reason': 'stop',
            }],
            'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
        })

    @staticmethod
    def _lectura_graph(request):
        """Graph solo se lee para saber qué números tiene cada WABA."""
        partes = [p for p in urlsplit(request.url).path.split('/') if p]
        if len(partes) >= 3 and partes[2] == 'phone_numbers':
            linea = {WABA_PRINCIPAL: LINEA_PRINCIPAL, WABA_LINEA_2: LINEA_2}.get(partes[1])
            datos = [{'id': linea.phone_id}] if linea else []
            return _respuesta(request, 200, {'data': datos})
        return _respuesta(request, 404, {'error': {'code': 100, 'message': 'arnés: lectura sin respuesta'}})

    def mensajes(self) -> list[Envio]:
        """Lo que la persona ve: sin reacciones de espera ni lecturas."""
        return [e for e in self.envios if e.es_mensaje]

    def marca(self) -> int:
        return len(self.envios)

    def desde(self, marca: int) -> list[Envio]:
        return [e for e in self.envios[marca:] if e.es_mensaje]


class RelojFijo:
    """`timezone.now()` parte de un instante fijo y avanza un microsegundo por lectura.

    El microsegundo evita empates al ordenar por fecha.
    """

    def __init__(self, inicio: datetime = INSTANTE_BASE):
        self._actual = inicio
        self._parche = None

    def ahora(self) -> datetime:
        self._actual += timedelta(microseconds=1)
        return self._actual

    def avanzar(self, **delta) -> datetime:
        self._actual += timedelta(**delta)
        return self._actual

    def iniciar(self) -> None:
        self._parche = patch('django.utils.timezone.now', new=self.ahora)
        self._parche.start()

    def detener(self) -> None:
        if self._parche is not None:
            self._parche.stop()
            self._parche = None


class Pausas:
    """`time.sleep` no espera; se anota cuánto se pidió."""

    def __init__(self):
        self.segundos: list[float] = []
        self._parche = None

    def iniciar(self) -> None:
        self._parche = patch('time.sleep', new=self.segundos.append)
        self._parche.start()

    def detener(self) -> None:
        if self._parche is not None:
            self._parche.stop()
            self._parche = None


@override_settings(**AJUSTES_LINEAS)
class ContratoLineaTestCase(TestCase):
    """Base de los contratos A2 a A6. Cada turno devuelve lo que salió en ese turno."""

    def setUp(self):
        super().setUp()
        self.salida = CapturaSalida()
        self.reloj = RelojFijo()
        self.pausas = Pausas()
        for pieza in (self.salida, self.reloj, self.pausas):
            pieza.iniciar()
            self.addCleanup(pieza.detener)
        entorno = patch.dict(os.environ, {'OPENAI_API_KEY': CLAVE_OPENAI_FALSA})
        entorno.start()
        self.addCleanup(entorno.stop)

    def publicar(self, payload: dict, *, firma: str | None = None):
        raw = json.dumps(payload).encode()
        return self.client.post(
            URL_WEBHOOK,
            data=raw,
            content_type='application/json',
            secure=True,
            HTTP_X_HUB_SIGNATURE_256=firmar(raw) if firma is None else firma,
        )

    def turno(self, telefono: str, mensaje: dict, *, linea: Linea = LINEA_PRINCIPAL) -> list[Envio]:
        marca = self.salida.marca()
        resp = self.publicar(payload_meta(linea, telefono, mensaje))
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        return self.salida.desde(marca)

    def escribir(self, telefono: str, texto: str, *, linea: Linea = LINEA_PRINCIPAL) -> list[Envio]:
        return self.turno(telefono, mensaje_texto(texto), linea=linea)

    def tocar(self, telefono: str, id_boton: str, titulo: str = '', *, linea: Linea = LINEA_PRINCIPAL) -> list[Envio]:
        return self.turno(telefono, mensaje_boton(id_boton, titulo), linea=linea)

    def elegir(self, telefono: str, id_fila: str, titulo: str = '', *, linea: Linea = LINEA_PRINCIPAL) -> list[Envio]:
        return self.turno(telefono, mensaje_lista(id_fila, titulo), linea=linea)

    def lanzar_campana(self, estudiantes, *, linea: Linea = LINEA_PRINCIPAL, nombre: str = 'inicio') -> list[Envio]:
        """Campaña de inicio de flujo aprobada, por la WABA de esa línea."""
        from core.meta_waba import ejecutar_campana_meta
        from core.models_campana_meta import CampanaMeta, PlantillaMeta

        waba = WABA_LINEA_2 if linea == LINEA_2 else WABA_PRINCIPAL
        plantilla = PlantillaMeta.objects.create(
            nombre_interno=f'Contrato {nombre}',
            meta_name=f'contrato_{nombre}_{next(_wamids)}',
            idioma='es',
            categoria='MARKETING',
            tipo='TEXTO',
            cuerpo='Hola {{1}}',
            estado='APPROVED',
            activa=True,
            waba_id=waba,
            boton_1_tipo='QUICK_REPLY',
            boton_1_texto='Iniciar',
        )
        campana = CampanaMeta.objects.create(
            nombre=f'Contrato {nombre}',
            plantilla=plantilla,
            phone_number_id=linea.phone_id,
            es_inicio_flujo=True,
        )
        campana.destinatarios.add(*estudiantes)
        marca = self.salida.marca()
        resultado = ejecutar_campana_meta(campana)
        self.assertEqual(resultado.get('fallidos'), 0, resultado)
        return self.salida.desde(marca)


def crear_curso(nombre: str, *, modulos: int = 2, cliente=None, catalogo: bool = False, orden: int = 0):
    """Curso activo sin espera entre módulos. Cada módulo trae CONTENIDO_<nombre>_<n>."""
    from core.models import Curso, Modulo

    curso = Curso.objects.create(
        nombre=nombre,
        descripcion=f'Descripción de {nombre}',
        cliente=cliente,
        activo=True,
        catalogo_menu=catalogo,
        orden=orden,
        dias_espera_entre_modulos=0,
    )
    for numero in range(1, modulos + 1):
        Modulo.objects.create(
            curso=curso,
            numero=numero,
            titulo=f'{nombre} M{numero}',
            descripcion='d',
            contenido=f'CONTENIDO_{nombre}_{numero}',
        )
    return curso
