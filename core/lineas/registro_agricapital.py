"""Bienvenida y cohorte AgriCapital en la línea 3.

Solo corre si EKI_AGRICAPITAL_CLIENTE_ID coincide con el enlace.
Vacío = la línea 3 sigue igual para todos los clientes.
Mete al grupo OP1 con los cursos del carrusel (cursos_whatsapp).
No inscribe curso: eso lo hace Ver curso del carrusel.
"""
from __future__ import annotations

import logging
import unicodedata

logger = logging.getLogger(__name__)

# Cuerpo del Flow (un solo mensaje): el CTA abre el formulario.
TEXTO_BIENVENIDA = (
    '¡Qué bueno tenerte aquí! Estás a pocos pasos de empezar tu curso por WhatsApp. '
    'Toca *«Registrarme»* para comenzar.'
)
NOMBRE_PUBLICO = 'AgriCapital'
BOTON_ID_PREFIJO = 'registro-abrir-C'
CTA_BIENVENIDA = 'Registrarme'
# Canónica en el wa.me/QR. El match ignora mayúsculas, tildes y puntuación.
FRASE_ENLACE = 'Hola, AgriCapital me invitó a un curso gratis'
# Claves ya normalizadas (_norm_frase). Aliases cortos y QR viejos.
FRASES_AGRI = frozenset({
    'HOLA AGRICAPITAL ME INVITO A UN CURSO GRATIS',
    'HOLA AGRICAPITAL ME INVITO A 1 CURSO GRATIS',
    'HOLA AGRICAPITAL',
    'HOLA EKI AGRI',
    'EKI AGRI',
})
NOMBRE_GRUPO_COHORTE = 'AgriCapital · cohorte noviembre'


def _norm_frase(frase: str) -> str:
    """Mayúsculas, sin tildes ni puntuación; espacios colapsados."""
    texto = unicodedata.normalize('NFD', ' '.join((frase or '').split()).upper())
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    for ch in ',.;:¡!¿?()[]{}"\'':
        texto = texto.replace(ch, ' ')
    return ' '.join(texto.split())


def cliente_id_configurado() -> int | None:
    from django.conf import settings

    bruto = str(getattr(settings, 'EKI_AGRICAPITAL_CLIENTE_ID', '') or '').strip()
    if not bruto.isdigit():
        return None
    return int(bruto)


def es_cliente_agricapital(cliente_id: int | None) -> bool:
    configurado = cliente_id_configurado()
    return configurado is not None and cliente_id == configurado


def nombre_publico(cliente) -> str:
    """Nombre para mensajes. AgriCapital siempre con A y C mayúsculas."""
    if cliente is None:
        return NOMBRE_PUBLICO
    if es_cliente_agricapital(getattr(cliente, 'pk', None)):
        return NOMBRE_PUBLICO
    return (getattr(cliente, 'nombre', None) or NOMBRE_PUBLICO).strip() or NOMBRE_PUBLICO


def frase_enlace_agricapital() -> str:
    """Texto del enlace/QR. Vacío si AgriCapital no está configurado."""
    if cliente_id_configurado() is None:
        return ''
    return FRASE_ENLACE


def frase_para_cliente(cliente_id: int) -> str | None:
    """Frase pública del enlace si este cliente es AgriCapital; si no, None."""
    if not es_cliente_agricapital(int(cliente_id)):
        return None
    return FRASE_ENLACE


def destino_frase_agri(frase: str) -> tuple[str, int] | None:
    """('cliente', id) si la frase es la de AgriCapital; None si no."""
    if _norm_frase(frase) not in FRASES_AGRI:
        return None
    cliente_id = cliente_id_configurado()
    if cliente_id is None:
        return None
    return ('cliente', cliente_id)


def es_enlace_agricapital(cliente_id: int | None, body: str) -> bool:
    """True si este mensaje es la frase/enlace de AgriCapital."""
    if destino_frase_agri(body):
        return True
    from core.lineas.registro_enlace import leer_frase

    destino = leer_frase(body)
    if not (destino and destino[0] == 'cliente'):
        return False
    return es_cliente_agricapital(destino[1])


def es_boton_registrarme(body: str) -> int | None:
    """Id de cliente si tocó Registrarme de la bienvenida AgriCapital."""
    texto = (body or '').strip()
    if not texto.startswith(BOTON_ID_PREFIJO):
        return None
    resto = texto[len(BOTON_ID_PREFIJO):]
    if not resto.isdigit():
        return None
    cliente_id = int(resto)
    if not es_cliente_agricapital(cliente_id):
        return None
    return cliente_id


def mandar_bienvenida(telefono: str, cliente_id: int) -> bool:
    """Bienvenida con botón Registrarme. True si Meta aceptó el envío."""
    from django.db import DatabaseError
    from requests import RequestException

    from core.lineas.envio import enviar_meta_botones

    try:
        resultado = enviar_meta_botones(
            telefono,
            TEXTO_BIENVENIDA,
            [(f'{BOTON_ID_PREFIJO}{int(cliente_id)}', CTA_BIENVENIDA)],
            agente_evento='registro_agricapital',
        )
    except (DatabaseError, RequestException, OSError, TypeError, ValueError):
        logger.exception('registro_agricapital_bienvenida')
        return False
    return bool(resultado and resultado.get('success'))


enviar_bienvenida = mandar_bienvenida


def _id_setting(nombre: str) -> int | None:
    from django.conf import settings

    bruto = str(getattr(settings, nombre, '') or '').strip()
    if not bruto.isdigit():
        return None
    return int(bruto)


def cursos_del_carrusel(cliente):
    """Los del carrusel WhatsApp; si no marcó, los activos de la empresa."""
    from core.models import Curso

    seleccion = list(cliente.cursos_whatsapp.filter(activo=True).order_by('orden', 'nombre', 'id'))
    if seleccion:
        return seleccion
    return list(
        Curso.objects.filter(cliente=cliente, activo=True).order_by('orden', 'nombre', 'id')
    )


def asegurar_grupo_cohorte(cliente):
    """Grupo OP1 de la cohorte. Reusa EKI_AGRICAPITAL_GRUPO_ID o lo crea."""
    from django.db import DatabaseError

    from core.models.opciones import PLAN_CURSO_ASESOR
    from core.models_extras import GrupoEstudiantes

    grupo_id = _id_setting('EKI_AGRICAPITAL_GRUPO_ID')
    try:
        if grupo_id is not None:
            grupo = GrupoEstudiantes.objects.filter(
                pk=grupo_id, cliente_id=cliente.pk, activo=True,
            ).first()
            if grupo is None:
                logger.warning('registro_agricapital_grupo_ausente id=%s', grupo_id)
                return None
        else:
            grupo, _creado = GrupoEstudiantes.objects.get_or_create(
                cliente=cliente,
                nombre=NOMBRE_GRUPO_COHORTE,
                defaults={
                    'plan_linea_meta': PLAN_CURSO_ASESOR,
                    'activo': True,
                    'descripcion': 'Cohorte AgriCapital línea 3 · OP1',
                },
            )
        if (grupo.plan_linea_meta or '') != PLAN_CURSO_ASESOR:
            grupo.plan_linea_meta = PLAN_CURSO_ASESOR
            grupo.save(update_fields=['plan_linea_meta'])
        if not grupo.activo:
            grupo.activo = True
            grupo.save(update_fields=['activo'])
        cursos = cursos_del_carrusel(cliente)
        if cursos:
            grupo.cursos.set(cursos)
        return grupo
    except DatabaseError:
        logger.exception('registro_agricapital_grupo')
        return None


def aplicar_cohorte(est, cliente) -> None:
    """Mete al grupo OP1 con los cursos del carrusel. Sin inscripción aún."""
    if cliente is None or not es_cliente_agricapital(getattr(cliente, 'pk', None)):
        return
    if getattr(est, 'cliente_id', None) != getattr(cliente, 'pk', None):
        return
    grupo = asegurar_grupo_cohorte(cliente)
    if grupo is not None:
        _agregar_al_grupo(grupo, est)


def _agregar_al_grupo(grupo, est) -> None:
    from django.db import DatabaseError

    try:
        grupo.estudiantes.add(est)
    except DatabaseError:
        logger.exception('registro_agricapital_grupo_add')
