"""Entrega unificada del diploma por la línea (Sender).

Plantilla Meta si hay nombre configurado; si no, imagen de sesión.
Marca `Certificado.enviado_whatsapp` solo cuando Graph confirma éxito.
Vistas y admin reexportan desde `core.views.diploma_meta` (fachada estable).
"""
from __future__ import annotations

import logging
import re

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

_MARCAS_DIPLOMA = (
    '¡tu certificado',
    '¡su certificado',
    'certificado digital está listo',
    '— certificado *',
)
_CODIGO_EN_URL = re.compile(r'certificado_(eki-[A-Za-z0-9-]+)\.(?:png|jpe?g|webp)', re.I)


def es_entrega_diploma(texto: str, media_url: str | None = None) -> bool:
    """True solo si el mensaje es la imagen del diploma, no un video de clase."""
    if not str(media_url or '').strip():
        return False
    t = (texto or '').lower()
    return any(marca in t for marca in _MARCAS_DIPLOMA)


def nombre_plantilla_diploma() -> str:
    """Entorno gana. Si está vacío, el nombre de Configuración Global."""
    env = (getattr(settings, 'META_TEMPLATE_DIPLOMA', '') or '').strip()
    if env:
        return env
    try:
        from core.models import ConfiguracionGlobal
        return (ConfiguracionGlobal.get_solo().meta_plantilla_diploma or '').strip()
    except Exception:
        logger.exception('diploma_entrega_nombre_plantilla')
        return ''


def enviar_diploma_plantilla_meta(
    telefono,
    media_url,
    *,
    nombre_estudiante: str = '',
    curso: str = '',
    codigo: str = '',
) -> dict | None:
    """None si no hay plantilla. El caller sigue con imagen de sesión."""
    nombre = nombre_plantilla_diploma()
    if not nombre or not str(media_url or '').strip():
        return None
    idioma = (getattr(settings, 'META_TEMPLATE_DIPLOMA_IDIOMA', 'es') or 'es').strip() or 'es'
    variables = {
        '1': (nombre_estudiante or 'estudiante')[:1024],
        '2': (curso or 'curso')[:1024],
        '3': (codigo or '')[:1024],
    }
    from core.lineas.sender import sender_de_linea

    sender = sender_de_linea()
    if getattr(sender, 'canal', '') == 'meta':
        return sender.plantilla_imagen(
            telefono,
            nombre,
            media_url,
            variables,
            idioma=idioma,
            agente='diploma_meta',
        )

    from core.canal.sandbox_canal import enviar_meta_plantilla_imagen

    return enviar_meta_plantilla_imagen(
        telefono,
        nombre,
        media_url,
        variables,
        idioma=idioma,
        agente_evento='diploma_meta',
    )


def entregar_si_corresponde(
    telefono: str,
    texto: str,
    media_url: str | None = None,
    *,
    agente: str = '',
) -> dict | None:
    """None si no es diploma. Si lo es, plantilla → sesión y alinea el flag."""
    if not es_entrega_diploma(texto, media_url):
        return None

    nombre, curso_nombre, codigo, cert = _datos_certificado(telefono, media_url)
    if cert is not None:
        from core.certificados.nota_antes_diploma import omite_diploma_sin_nota

        if omite_diploma_sin_nota(cert.estudiante, cert.curso):
            logger.info('diploma_omitido_sin_nota cert=%s', cert.pk)
            return {
                'success': False,
                'mensaje_id': None,
                'response': 'sin_nota_cierre',
                'modo': 'sin_nota',
            }
    r_tpl = enviar_diploma_plantilla_meta(
        telefono,
        media_url,
        nombre_estudiante=nombre,
        curso=curso_nombre,
        codigo=codigo,
    )
    if r_tpl and r_tpl.get('success'):
        _marcar_enviado(cert, telefono)
        return {**r_tpl, 'modo': 'plantilla_meta'}

    if r_tpl is not None:
        logger.warning('diploma_entrega_plantilla_fallo; se intenta imagen de sesión')

    resultado = _enviar_sesion(telefono, texto, media_url, agente=agente or 'diploma_meta')
    if resultado and resultado.get('success'):
        _marcar_enviado(cert, telefono)
        return {**resultado, 'modo': 'sesion_meta'}
    return resultado or {'success': False, 'mensaje_id': None, 'response': 'diploma_envio_fallo'}


def _enviar_sesion(telefono: str, texto: str, media_url: str | None, *, agente: str) -> dict:
    from core.lineas.sender import sender_de_linea

    sender = sender_de_linea()
    if getattr(sender, 'canal', '') == 'meta':
        return sender.texto(telefono, texto, media_url=media_url, agente=agente)

    from core.canal.sandbox_canal import enviar_meta

    return enviar_meta(
        telefono,
        texto,
        media_url=media_url,
        canal_evento='certificado',
        agente_evento=agente,
    )


def _digitos_telefono(valor: str) -> str:
    return ''.join(c for c in str(valor or '') if c.isdigit())


def _codigo_desde_media(media_url: str | None) -> str:
    m = _CODIGO_EN_URL.search(str(media_url or ''))
    return (m.group(1) if m else '').strip()


def _db_o_nada(fn, default=None):
    """SimpleTestCase sin DB no debe tumbar el envío del diploma."""
    try:
        return fn()
    except Exception as e:
        if e.__class__.__name__ == 'DatabaseOperationForbidden':
            return default
        raise


def _datos_certificado(telefono: str, media_url: str | None):
    """Nombre, curso, código y fila Certificado si se puede resolver sin ambigüedad."""
    codigo_url = _codigo_desde_media(media_url)

    def _buscar():
        from core.models import Estudiante
        from core.certificados.models_certificados import Certificado

        cert = None
        if codigo_url:
            cert = Certificado.objects.filter(codigo_verificacion=codigo_url).first()
        if cert is None:
            digits = _digitos_telefono(telefono)
            if len(digits) >= 10:
                qs = Estudiante.objects.filter(telefono__endswith=digits[-10:])
                n = qs.count()
                if n == 1:
                    cert = (
                        Certificado.objects.filter(estudiante=qs.get())
                        .order_by('-id')
                        .first()
                    )
                elif n != 1:
                    logger.warning('diploma_entrega_tel_ambiguo n=%s', n)
        return cert

    cert = _db_o_nada(_buscar, None)
    if not cert:
        return '', '', codigo_url, None

    est = cert.estudiante
    curso = cert.curso
    return (
        (getattr(est, 'nombre', '') or '')[:1024],
        (getattr(curso, 'nombre', '') or '')[:1024],
        (cert.codigo_verificacion or codigo_url or '')[:1024],
        cert,
    )


def _marcar_enviado(cert, telefono: str) -> None:
    """Alinea admin con el chat. No pisa un envío ya marcado."""

    def _aplicar():
        from core.models import Estudiante
        from core.certificados.models_certificados import Certificado

        objetivo = cert
        if objetivo is None:
            digits = _digitos_telefono(telefono)
            if len(digits) < 10:
                return
            qs = Estudiante.objects.filter(telefono__endswith=digits[-10:])
            if qs.count() != 1:
                return
            objetivo = (
                Certificado.objects.filter(estudiante=qs.get())
                .order_by('-id')
                .first()
            )
        if not objetivo or objetivo.enviado_whatsapp:
            return
        objetivo.enviado_whatsapp = True
        objetivo.fecha_envio = timezone.now()
        objetivo.save(update_fields=['enviado_whatsapp', 'fecha_envio'])

    try:
        _db_o_nada(_aplicar)
    except Exception:
        logger.exception('diploma_entrega_marca_envio')
