"""
Carrusel demo de programas (solo prospectos / números no guardados como Estudiante).

Ver docs/WHATSAPP_CARRUSEL_DEMO_PROGRAMAS.md

Por card (2 botones, mismo orden en todas):
  1) Ver descripción  → desc_<slug>
  2) Quiero demo / Solo info → in_riendas | info_<slug>
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

KEYWORDS_CARRUSEL = frozenset({
    'programas',
    'programa',
    'catalogo',
    'catálogo',
    'cursos',
    'ver programas',
    'ver cursos',
    '4',
    '4️⃣',
})

# Tras descripción de Riendas: seguir o no
KEYWORDS_SEGUIR_RIENDAS = frozenset({
    'quiero demo',
    'quiero la demo',
    'si quiero',
    'sí quiero',
    'si, quiero',
    'sí, quiero',
    'seguir',
    'inscribirme demo',
    'in_riendas',
})
KEYWORDS_NO_SEGUIR = frozenset({
    'no gracias',
    'no, gracias',
    'solo mirar',
    'despues',
    'después',
})

DESC_AGROSAVIA = (
    "🌾 *Agrosavia · formación de campo*\n\n"
    "Así se ve un programa técnico en eki: lecciones cortas por WhatsApp, "
    "ejemplos de finca y un cierre práctico.\n\n"
    "⚠️ *Solo muestra* en esta demo: no abre inscripción.\n\n"
    "La demo real es *Tome las riendas de su dinero*. "
    "Escriba *programas* para volver al carrusel, o *riendas* para esa demo."
)

DESC_FEDEPALMA = (
    "🌴 *Fedepalma · buenas prácticas*\n\n"
    "Ejemplo de cómo eki lleva un programa sectorial: módulos claros, "
    "ritmo con *listo* y acompañamiento por chat.\n\n"
    "⚠️ *Solo muestra*: no inicia curso.\n\n"
    "Pruebe la demo *Tome las riendas* escribiendo *riendas*, "
    "o *programas* para el carrusel."
)

DESC_PROFAMILIA = (
    "💚 *Profamilia · bienestar*\n\n"
    "Ejemplo de programa de bienestar en el formato eki: mensajes cortos, "
    "tono cercano y avance paso a paso por WhatsApp.\n\n"
    "⚠️ *Solo muestra*: no abre inscripción.\n\n"
    "La demo activa es *Tome las riendas de su dinero* → escriba *riendas*."
)

DESC_EMPRENDIMIENTO = (
    "🌱 *Emprendimiento Agro Rural*\n\n"
    "Así se ve un programa eki para crear y fortalecer un negocio rural: "
    "ideas claras, pasos cortos por WhatsApp y foco en la finca.\n\n"
    "⚠️ *Solo muestra* en esta vitrina: no abre inscripción.\n\n"
    "La demo real es *Tome las riendas de su dinero* → *riendas*."
)

DESC_MAQUINARIA = (
    "🛠️ *Maquinaria y herramientas para el agro*\n\n"
    "Ejemplo de formación práctica eki: equipos, uso seguro y buenas "
    "prácticas en campo, en lecciones cortas por chat.\n\n"
    "⚠️ *Solo muestra*: no inicia curso.\n\n"
    "Pruebe la demo *Tome las riendas* → *riendas*."
)

DESC_COMERCIALIZACION = (
    "🛒 *Comercialización y ventas*\n\n"
    "Así enseña eki a llevar el producto al mercado: clientes, precio y "
    "ventas con mensajes accionables por WhatsApp.\n\n"
    "⚠️ *Solo muestra*: no abre inscripción.\n\n"
    "Demo activa: *Tome las riendas* → *riendas*."
)

DESC_AGRODIGITAL = (
    "📱 *Agricultura digital e IA para el campo*\n\n"
    "Vitrina de cómo eki acerca datos, apps e inteligencia artificial "
    "al productor, en formato móvil y paso a paso.\n\n"
    "⚠️ *Solo muestra*: no inicia curso.\n\n"
    "Para la demo real escriba *riendas*."
)

DESC_RIENDAS = (
    "💰 *Tome las riendas de su dinero* (demo eki)\n\n"
    "Ordene ingresos y gastos, tome decisiones simples y aplique lo aprendido "
    "en la semana — todo por WhatsApp, a su ritmo.\n\n"
    "Esta es la *única* tarjeta que abre contacto real de demo.\n\n"
    "✅ Si quiere seguir: escriba *quiero demo*\n"
    "👀 Si solo estaba mirando: escriba *no gracias*\n"
    "📚 Carrusel otra vez: *programas*"
)

TEXTO_CTA_RIENDAS = (
    "🚀 *¡Vamos con la demo!*\n\n"
    "*Tome las riendas de su dinero* — formación práctica eki por WhatsApp.\n\n"
    "Para que un asesor lo contacte:\n"
    "👉 Escriba *1* (eki para mi empresa) y luego su *correo*.\n\n"
    "O escriba *programas* si quiere ver el carrusel otra vez."
)

TEXTO_INFO_VITRINA = (
    "ℹ️ *Solo información*\n\n"
    "Esa tarjeta es una *muestra visual* de cómo se ven los programas en eki. "
    "No inscribe ni abre un curso.\n\n"
    "La demo que sí inicia contacto es *Tome las riendas de su dinero*.\n"
    "Escriba *riendas* o *programas*."
)

TEXTO_NO_SEGUIR = (
    "Perfecto, sin compromiso 🙂\n\n"
    "Cuando quiera, escriba *programas* para ver el carrusel "
    "o *riendas* si se anima a la demo de finanzas."
)

TEXTO_FALLBACK_LISTA = (
    "✨ *Así se aprende con eki*\n\n"
    "Deslice con la imaginación (el carrusel con fotos se activa "
    "cuando Meta apruebe la plantilla):\n\n"
    "🌾 Agrosavia — *Ver descripción* / Solo info\n"
    "🌴 Fedepalma — *Ver descripción* / Solo info\n"
    "💰 *eki · Riendas* — *Ver descripción* / *Quiero demo*\n"
    "💚 Profamilia — *Ver descripción* / Solo info\n\n"
    "Escriba *riendas* para la demo, *descripcion riendas* para leerla, "
    "o *1* si es empresa."
)

# Mapa payload → respuesta
_RESPUESTAS_PAYLOAD: dict[str, str] = {
    'desc_agrosavia': DESC_AGROSAVIA,
    'desc_fedepalma': DESC_FEDEPALMA,
    'desc_profamilia': DESC_PROFAMILIA,
    'desc_riendas': DESC_RIENDAS,
    'desc_emprendimiento': DESC_EMPRENDIMIENTO,
    'desc_maquinaria': DESC_MAQUINARIA,
    'desc_comercializacion': DESC_COMERCIALIZACION,
    'desc_agrodigital': DESC_AGRODIGITAL,
    'in_riendas': TEXTO_CTA_RIENDAS,
    'info_agrosavia': TEXTO_INFO_VITRINA,
    'info_fedepalma': TEXTO_INFO_VITRINA,
    'info_profamilia': TEXTO_INFO_VITRINA,
    'info_emprendimiento': TEXTO_INFO_VITRINA,
    'info_maquinaria': TEXTO_INFO_VITRINA,
    'info_comercializacion': TEXTO_INFO_VITRINA,
    'info_agrodigital': TEXTO_INFO_VITRINA,
    # Compat payloads v1 (un botón)
    'demo_riendas': TEXTO_CTA_RIENDAS,
    'demo_vitrina_agrosavia': DESC_AGROSAVIA,
    'demo_vitrina_fedepalma': DESC_FEDEPALMA,
    'demo_vitrina_profamilia': DESC_PROFAMILIA,
}


def demo_carousel_habilitado() -> bool:
    return bool(getattr(settings, 'EKI_DEMO_CAROUSEL_ENABLED', True))


def content_sid_carrusel() -> str:
    return str(getattr(settings, 'EKI_DEMO_CAROUSEL_CONTENT_SID', '') or '').strip()


def es_keyword_carrusel(texto: str) -> bool:
    t = (texto or '').strip().lower().replace('*', '').strip()
    return t in KEYWORDS_CARRUSEL


def es_payload_carrusel(payload: str) -> bool:
    p = (payload or '').strip()
    if p in _RESPUESTAS_PAYLOAD:
        return True
    if p.startswith(('desc_', 'info_', 'in_', 'demo_vitrina_', 'demo_')):
        return True
    return False


def respuesta_por_payload(payload: str) -> str:
    p = (payload or '').strip()
    if p in _RESPUESTAS_PAYLOAD:
        return _RESPUESTAS_PAYLOAD[p]
    if p.startswith('desc_') or p.startswith('demo_vitrina_'):
        return TEXTO_INFO_VITRINA
    if p.startswith('info_'):
        return TEXTO_INFO_VITRINA
    if p in {'in_riendas', 'demo_riendas'}:
        return TEXTO_CTA_RIENDAS
    return TEXTO_FALLBACK_LISTA


def _digitos_telefono(raw: str) -> str:
    import re

    d = re.sub(r'\D', '', raw or '')
    if len(d) == 10:
        d = f'57{d}'
    return d


def curso_demo_riendas():
    """Copia de Riendas para la demo pública. None = no arrancar curso."""
    raw = str(getattr(settings, 'EKI_DEMO_RIENDAS_CURSO_ID', '') or '').strip()
    if not raw.isdigit():
        return None
    from core.models import Curso

    return (
        Curso.objects.filter(pk=int(raw), activo=True)
        .select_related('cliente')
        .first()
    )


def sincronizar_demo_riendas_desde_prod(*, origen_id: int | None = None) -> dict:
    """
    Copia contenido + ArchivoModulo (videos/audio) del Riendas prod → curso demo.
    No borra el curso; actualiza por número de módulo. Reutiliza las mismas URLs S3.
    """
    from core.models import Curso, Modulo
    from core.models_extras import ArchivoModulo

    destino = curso_demo_riendas()
    if destino is None:
        return {'ok': False, 'error': 'sin_demo'}

    oid = origen_id
    if oid is None:
        try:
            oid = int(getattr(settings, 'EKI_DEMO_RIENDAS_ORIGEN_ID', 3) or 3)
        except (TypeError, ValueError):
            oid = 3
    origen = Curso.objects.filter(pk=oid, activo=True).first()
    if origen is None:
        return {'ok': False, 'error': 'sin_origen', 'origen_id': oid}

    actualizados = 0
    archivos_copiados = 0
    for mod_o in Modulo.objects.filter(curso=origen).order_by('numero'):
        mod_d = Modulo.objects.filter(curso=destino, numero=mod_o.numero).first()
        if mod_d is None:
            mod_d = Modulo.objects.create(
                curso=destino,
                numero=mod_o.numero,
                titulo=mod_o.titulo,
                descripcion=mod_o.descripcion or '',
                contenido=mod_o.contenido or '',
                modo_entrega=mod_o.modo_entrega,
                publicado_wa=True,
            )
            actualizados += 1
        else:
            dirty = False
            for field in (
                'titulo',
                'descripcion',
                'contenido',
                'modo_entrega',
                'video_url',
                'archivo_pdf_url',
                'imagen_portada_url',
            ):
                if not hasattr(mod_o, field) or not hasattr(mod_d, field):
                    continue
                val = getattr(mod_o, field)
                if getattr(mod_d, field) != val:
                    setattr(mod_d, field, val)
                    dirty = True
            if hasattr(mod_d, 'publicado_wa') and not mod_d.publicado_wa:
                mod_d.publicado_wa = True
                dirty = True
            if dirty:
                mod_d.save()
                actualizados += 1

        # Multimedia: clonar ArchivoModulo por orden/titulo (mismas URLs S3)
        for a_o in ArchivoModulo.objects.filter(modulo=mod_o, activo=True).order_by('orden', 'id'):
            existe = ArchivoModulo.objects.filter(
                modulo=mod_d,
                titulo=a_o.titulo,
                tipo=a_o.tipo,
                orden=a_o.orden,
            ).exists()
            if existe:
                continue
            nuevo = ArchivoModulo(
                modulo=mod_d,
                tipo=a_o.tipo,
                titulo=a_o.titulo,
                descripcion=a_o.descripcion or '',
                url_externa=a_o.url_externa or '',
                disponible_offline=a_o.disponible_offline,
                orden=a_o.orden,
                activo=True,
                tamano_bytes=a_o.tamano_bytes,
                duracion_segundos=a_o.duracion_segundos,
            )
            if a_o.archivo:
                nuevo.archivo = a_o.archivo
            try:
                # bulk_create evita HEAD de validación en url_externa (URLs ya OK en origen)
                ArchivoModulo.objects.bulk_create([nuevo])
                archivos_copiados += 1
            except Exception:
                logger.exception(
                    'sync_demo_archivo_fail origen=%s destino_mod=%s titulo=%s',
                    a_o.id,
                    mod_d.id,
                    a_o.titulo,
                )

    return {
        'ok': True,
        'origen_id': origen.id,
        'destino_id': destino.id,
        'modulos_actualizados': actualizados,
        'archivos_copiados': archivos_copiados,
    }


def _reset_progreso_demo(progreso, curso) -> None:
    from core.inscripcion_curso import primer_modulo_curso
    from core.models import ModuloCompletado

    m1 = primer_modulo_curso(curso)
    progreso.completado = False
    progreso.fecha_completado = None
    progreso.modulo_actual = m1
    progreso.paso_actual_modulo = 1
    progreso.esperando_respuesta_evaluacion_paso = False
    progreso.paso_evaluacion_paso = None
    progreso.save(
        update_fields=[
            'completado',
            'fecha_completado',
            'modulo_actual',
            'paso_actual_modulo',
            'esperando_respuesta_evaluacion_paso',
            'paso_evaluacion_paso',
        ]
    )
    ModuloCompletado.objects.filter(progreso=progreso).delete()


def _enviar_modulo1_demo(dest: str, curso) -> None:
    """Manda texto + multimedia del módulo 1 para que el usuario vea el curso al instante."""
    from core.inscripcion_curso import primer_modulo_curso
    from core.models_extras import ArchivoModulo
    from core.response_templates import dividir_contenido_seguro
    from core.utils import enviar_whatsapp_twilio
    from core.whatsapp_service import enviar_archivo_modulo_whatsapp

    m1 = primer_modulo_curso(curso)
    if m1 is None:
        enviar_whatsapp_twilio(
            dest,
            'Demo *Tome las riendas* lista, pero aún no hay módulos. Avisa a eki tech.',
        )
        return
    intro = (
        f'📚 *Demo sandbox · {curso.nombre}*\n'
        f'Módulo {m1.numero}: {m1.titulo}\n\n'
        '_Escribe *listo* para avanzar. *menu* vuelve al menú._\n'
    )
    enviar_whatsapp_twilio(dest, intro)
    body = (m1.contenido or '').strip()
    if body:
        for chunk in dividir_contenido_seguro(body, max_chars=1200):
            enviar_whatsapp_twilio(dest, chunk)
    archivos = list(
        ArchivoModulo.objects.filter(modulo=m1, activo=True).order_by('orden', 'id')
    )
    if not archivos and not body:
        enviar_whatsapp_twilio(
            dest,
            'Este módulo aún no tiene contenido. Escribe *listo* por si hay media.',
        )
        return
    for arch in archivos:
        try:
            enviar_archivo_modulo_whatsapp(dest, arch)
        except Exception:
            logger.exception('demo_riendas_envio_archivo_fail archivo=%s', arch.id)


def arrancar_demo_riendas(*, telefono: str, dest_wa: str, sandbox: bool = False) -> bool:
    """
    Inscribe en la copia demo de Riendas y manda Habeas.
    Si no hay curso configurado, manda el CTA de *1* + correo.

    sandbox=True: permite números ya inscritos en otro cliente, resetea progreso
    y envía el módulo 1 (uso menú sandbox Twilio).
    """
    from core.utils import enviar_whatsapp_twilio
    from core.whatsapp_service import enviar_habeas_data

    dest = dest_wa or telefono
    if sandbox:
        try:
            sincronizar_demo_riendas_desde_prod()
        except Exception:
            logger.exception('Demo Riendas: sync desde prod falló (sigo con demo actual)')

    curso = curso_demo_riendas()
    if curso is None:
        enviar_whatsapp_twilio(dest, TEXTO_CTA_RIENDAS)
        return True

    from core.inscripcion_curso import inscribir_estudiante_en_curso
    from core.models import Estudiante, ProspectoB2B

    tel = _digitos_telefono(telefono) or _digitos_telefono(dest)
    if not tel:
        enviar_whatsapp_twilio(dest, TEXTO_CTA_RIENDAS)
        return True

    est = Estudiante.objects.filter(telefono=tel).select_related('cliente').first()
    if est is not None:
        mismo_cliente = (
            est.cliente_id
            and curso.cliente_id
            and est.cliente_id == curso.cliente_id
        )
        if not mismo_cliente and not sandbox:
            enviar_whatsapp_twilio(
                dest,
                'Usted ya está en un curso eki. Esta demo pública es para números nuevos.\n\n'
                'Si quiere ver la página: https://eki.com.co/programas/tome-las-riendas',
            )
            return True
        progreso, _ = inscribir_estudiante_en_curso(est, curso)
        if sandbox:
            _reset_progreso_demo(progreso, curso)
            ctx = dict(est.contexto_temporal or {})
            ctx['curso_activo_id'] = curso.id
            est.contexto_temporal = ctx
            if est.estado_chat != 'ACTIVO' and est.acepto_terminos:
                est.estado_chat = 'ACTIVO'
            est.save(update_fields=['contexto_temporal', 'estado_chat'])
            if not est.acepto_terminos:
                est.estado_chat = 'ESPERANDO_HABEAS_DATA'
                est.save(update_fields=['estado_chat'])
                enviar_habeas_data(tel, cliente=curso.cliente)
                return True
            _enviar_modulo1_demo(dest, curso)
            return True
        if not est.acepto_terminos:
            est.estado_chat = 'ESPERANDO_HABEAS_DATA'
            est.save(update_fields=['estado_chat'])
            enviar_habeas_data(tel, cliente=est.cliente)
            return True
        enviar_whatsapp_twilio(
            dest,
            'Ya está en la demo *Tome las riendas*. Escriba *listo* para continuar.',
        )
        return True

    nombre = 'Participante demo'
    try:
        p = ProspectoB2B.objects.filter(telefono=tel).first()
        if p and (getattr(p, 'nombre_contacto', None) or '').strip():
            nombre = p.nombre_contacto.strip()[:100]
    except Exception:
        logger.exception('Demo Riendas: no se pudo leer prospecto')

    cedula = f'DEM{tel}'[:32]
    if Estudiante.objects.filter(cedula=cedula).exists():
        cedula = f'D{tel[-15:]}'[:32]

    est = Estudiante.objects.create(
        nombre=nombre,
        cedula=cedula,
        telefono=tel,
        cliente=curso.cliente,
        activo=True,
        acepto_terminos=False,
        estado_chat='ESPERANDO_HABEAS_DATA',
        estado_onboarding='nuevo',
    )
    progreso, _ = inscribir_estudiante_en_curso(est, curso)
    if sandbox:
        _reset_progreso_demo(progreso, curso)
        ctx = dict(est.contexto_temporal or {})
        ctx['curso_activo_id'] = curso.id
        est.contexto_temporal = ctx
        est.save(update_fields=['contexto_temporal'])
    enviar_whatsapp_twilio(
        dest,
        'Vamos con la demo *Tome las riendas de su dinero*. '
        'Primero el tratamiento de datos; si acepta, después escriba *listo*.',
    )
    enviar_habeas_data(tel, cliente=curso.cliente)
    return True


def respuesta_por_texto(texto: str) -> str | None:
    t = (texto or '').strip().lower().replace('*', '').strip()
    if t in KEYWORDS_SEGUIR_RIENDAS or t == 'riendas':
        return TEXTO_CTA_RIENDAS
    if t in KEYWORDS_NO_SEGUIR:
        return TEXTO_NO_SEGUIR
    if t in {
        'descripcion riendas',
        'descripción riendas',
        'ver descripcion riendas',
        'ver descripción riendas',
        'desc riendas',
    }:
        return DESC_RIENDAS
    if t in {'agrosavia', 'descripcion agrosavia', 'descripción agrosavia'}:
        return DESC_AGROSAVIA
    if t in {'fedepalma', 'descripcion fedepalma', 'descripción fedepalma'}:
        return DESC_FEDEPALMA
    if t in {'profamilia', 'descripcion profamilia', 'descripción profamilia'}:
        return DESC_PROFAMILIA
    # Títulos de botón que a veces llegan en Body
    if t == 'ver descripción' or t == 'ver descripcion':
        return None  # sin card id no sabemos cuál; pedir carrusel
    if t in {'quiero demo', 'solo info'}:
        return TEXTO_CTA_RIENDAS if 'demo' in t else TEXTO_INFO_VITRINA
    return None


def enviar_carrusel_demo(telefono: str) -> dict[str, Any]:
    """Envía plantilla carousel si hay Content SID; si no, lista en texto."""
    from core.whatsapp_service import enviar_template_twilio
    from core.utils import enviar_whatsapp_twilio

    sid = content_sid_carrusel()
    if sid.startswith('HX'):
        resultado = enviar_template_twilio(telefono, sid, variables=None)
        if resultado.get('success'):
            return resultado
        logger.warning(
            'Carrusel demo: falló envío HX=%s; fallback texto | %s',
            sid,
            resultado.get('response'),
        )
    return enviar_whatsapp_twilio(telefono, TEXTO_FALLBACK_LISTA)


def intentar_flujo_prospecto_carrusel(
    *,
    telefono: str,
    msg_from: str,
    msg_body: str,
    button_payload: str = '',
    solo_botones: bool = False,
) -> bool:
    """
    True si consumió el turno (envió respuesta y el caller debe return).

    Por defecto: prospectos (payloads + keywords *programas* / *4*).
    Con ``solo_botones=True``: también para Estudiante (taps del carrusel),
    sin robar *listo* ni el menú numérico del LMS.
    """
    if not demo_carousel_habilitado():
        return False

    payload = (button_payload or '').strip()
    if not payload:
        body_raw = (msg_body or '').strip()
        if es_payload_carrusel(body_raw):
            payload = body_raw

    if payload in {'in_riendas', 'demo_riendas'}:
        return arrancar_demo_riendas(
            telefono=telefono,
            dest_wa=msg_from or telefono,
        )

    if es_payload_carrusel(payload):
        from core.utils import enviar_whatsapp_twilio
        enviar_whatsapp_twilio(msg_from or telefono, respuesta_por_payload(payload))
        return True

    t_body = (msg_body or '').strip().lower().replace('*', '').strip()
    if t_body in KEYWORDS_SEGUIR_RIENDAS or t_body == 'riendas':
        if not solo_botones:
            return arrancar_demo_riendas(
                telefono=telefono,
                dest_wa=msg_from or telefono,
            )

    texto_card = respuesta_por_texto(msg_body)
    if texto_card:
        from core.utils import enviar_whatsapp_twilio
        enviar_whatsapp_twilio(msg_from or telefono, texto_card)
        return True

    if solo_botones:
        return False

    if es_keyword_carrusel(msg_body):
        enviar_carrusel_demo(msg_from or telefono)
        return True

    return False
