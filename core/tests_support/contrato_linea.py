"""Arnés de contratos de línea (fase A1 de PLAN_MODULARIDAD_EKI.md).

Un contrato escribe a una línea como lo haría Meta y mira lo que sale.
Nada llega a la red: lo que va por `requests` (Graph y Twilio) queda
capturado con una respuesta falsa; cualquier otro host falla, y `httpx`
(OpenAI, ElevenLabs) también. El reloj está fijo y las pausas de
`time.sleep` se anotan sin esperar.

El reloj solo cubre `django.utils.timezone.now`. Quien use
`datetime.now()` o `from django.utils.timezone import now` ve la hora real.
"""
from __future__ import annotations

import hashlib
import hmac
import itertools
import json
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

# 08:00 en Bogotá: el pico de la línea 2.
INSTANTE_BASE = datetime(2026, 10, 20, 13, 0, tzinfo=dt_timezone.utc)


@dataclass(frozen=True)
class Linea:
    phone_id: str
    e164: str
    nombre: str


LINEA_PRINCIPAL = Linea('100000000000001', '573009990001', 'Línea principal')
LINEA_2 = Linea('100000000000002', '573009990002', 'Línea 2')

AJUSTES_LINEAS = {
    'META_LINEAS': '',
    'SANDBOX_PROVEEDOR': 'meta',
    'SANDBOX_MENU_ENABLED': True,
    'WHATSAPP_PHONE_ID': LINEA_PRINCIPAL.phone_id,
    'SANDBOX_WHATSAPP_PHONE_ID': LINEA_PRINCIPAL.phone_id,
    'BOT_COMERCIAL_SANDBOX_NUMBER': LINEA_PRINCIPAL.e164,
    'WHATSAPP_PHONE_NUMBER_ID_2': LINEA_2.phone_id,
    'WHATSAPP_NUMERO_2_E164': LINEA_2.e164,
    'WHATSAPP_TOKEN': TOKEN_META,
    'WHATSAPP_APP_SECRET': SECRETO_META,
    'WHATSAPP_REQUIRE_SIGNATURE': True,
    'WEBHOOK_CELERY_ASYNC': False,
    'SANDBOX_CELERY_ASYNC': False,
    'NAT_WEBHOOK_CELERY_ASYNC': False,
    'CELERY_TASK_ALWAYS_EAGER': True,
    'SECURE_SSL_REDIRECT': False,
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
    cuerpo: dict = field(default_factory=dict)

    @property
    def es_mensaje(self) -> bool:
        return self.metodo == 'POST' and self.tipo != 'reaction'


def _texto_interactivo(inter: dict) -> tuple[str, list[str]]:
    texto = str((inter.get('body') or {}).get('text') or '')
    accion = inter.get('action') or {}
    botones = [
        str((b.get('reply') or {}).get('title') or '')
        for b in accion.get('buttons') or []
    ]
    for seccion in accion.get('sections') or []:
        botones.extend(str(f.get('title') or '') for f in seccion.get('rows') or [])
    if accion.get('button') and not botones:
        botones.append(str(accion.get('button')))
    for carta in accion.get('cards') or []:
        for b in (carta.get('action') or {}).get('buttons') or []:
            botones.append(str((b.get('quick_reply') or b.get('reply') or {}).get('title') or ''))
    return texto, [b for b in botones if b]


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
    texto, botones = '', []
    if tipo == 'text':
        texto = str((cuerpo.get('text') or {}).get('body') or '')
    elif tipo == 'interactive':
        texto, botones = _texto_interactivo(cuerpo.get('interactive') or {})
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
        self._ids = itertools.count(1)
        self._parches = []

    def iniciar(self) -> None:
        captura = self

        def enviar(_adapter, request, **_kwargs):
            return captura._atender(request)

        def httpx_bloqueado(_transport, request):
            captura.bloqueados.append(str(request.url))
            raise httpx.ConnectError('red bloqueada por el arnés de contratos', request=request)

        self._parches = [
            patch.object(HTTPAdapter, 'send', new=enviar),
            patch.object(httpx.HTTPTransport, 'handle_request', new=httpx_bloqueado),
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
                return _respuesta(request, 404, {'error': {'code': 100, 'message': 'arnés: GET sin respuesta'}})
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
