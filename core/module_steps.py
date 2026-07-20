"""Pasos internos por módulo (entrega progresiva por WhatsApp)."""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .models import Estudiante, Modulo, PasoModulo, ProgresoEstudiante

logger = logging.getLogger(__name__)

# CTAs tras entregar microcontenidos (WhatsApp); mismo verbo en todos los casos.
MSG_LISTO_ABRIR_SIGUIENTE_BLOQUE = (
    'Una vez termines de revisar el contenido, escribe *listo* '
    'para abrir el siguiente 👇'
)
MSG_LISTO_CONTINUAR_EN_MODULO = (
    'Una vez termines de revisar el contenido, escribe *listo* para continuar 👇'
)
MSG_LISTO_FIN_PASOS_MODULO = (
    'Una vez termines de revisar el contenido, escribe *listo* para pasar al '
    'siguiente módulo o paso del curso 👇'
)

from .response_templates import MENSAJE_CAPTION_SOLO_MEDIA, parte_mensaje_con_media

# Tras acertar evaluación de paso: un solo bubble (feedback + CTA) evita que WhatsApp
# entregue antes el texto corto de *listo* que el feedback más largo.
_CTA_LISTO_SIGUIENTE_MATERIAL_EVAL = (
    'Escribe *listo* para recibir el siguiente material 👇'
)


def mensaje_exito_eval_opciones_con_cta_listo(feedback_correcto_crudo: Optional[str]) -> str:
    raw = (feedback_correcto_crudo or '').strip()
    if not raw:
        raw = '✅ ¡Muy bien! Seguimos.'
    partes_fb = [p.strip() for p in raw.split('[SEP]') if p.strip()]
    cuerpo = '\n\n'.join(partes_fb) if partes_fb else raw
    return f'{cuerpo}\n\n{_CTA_LISTO_SIGUIENTE_MATERIAL_EVAL}'


def mensaje_neutro_avance_eval_con_cta_listo() -> str:
    """Tras omitir evaluación opción múltiple (p. ej. *listo* sin acertar): un solo bubble con CTA."""
    return f'📚 Seguimos con el curso.\n\n{_CTA_LISTO_SIGUIENTE_MATERIAL_EVAL}'


def mensaje_incorrecto_eval_opciones_con_cta_listo(feedback_incorrecto: str) -> str:
    """Tras fallar A–D: mismo bubble que el acierto (feedback + CTA *listo*)."""
    raw = (feedback_incorrecto or '').strip()
    if not raw:
        raw = '❌ *Respuesta incorrecta*\n\nRevisá las opciones e intentá de nuevo, o seguí cuando quieras.'
    return f'{raw}\n\n{_CTA_LISTO_SIGUIENTE_MATERIAL_EVAL}'


def _respuesta_cola_tras_avanzar_eval_opc(
    estudiante: Estudiante,
    progreso: ProgresoEstudiante,
    paso: PasoModulo,
    n: int,
    es_acierto: bool,
    head_override: Optional[str] = None,
) -> str:
    """
    Construye respuesta tras avanzar paso_actual_modulo y limpiar flags de evaluación.
    `paso` es el PasoModulo de evaluación que se acaba de cerrar.
    """
    if progreso.paso_actual_modulo > n:
        from .response_templates import get_response_for_intent

        tail = get_response_for_intent(
            'continuar_leccion',
            estudiante.nombre or 'Estudiante',
            estudiante_id=estudiante.id,
            mensaje_original='listo',
            _saltar_bloque_pasos_internos=True,
        )
        if es_acierto:
            head = head_override or (paso.feedback_correcto or '').strip() or '✅ ¡Muy bien! Seguimos.'
        else:
            head = '📚 Seguimos con el curso.'
        if tail and tail.startswith('[MULTI_MSG]'):
            resto = tail[len('[MULTI_MSG]') :].split('[SEP]')
            bloques = [p for p in resto if p]
            # Tras intento incorrecto ya dimos el CTA *listo* junto al feedback; no repetir este head.
            if not es_acierto and bloques:
                return unir_multimsg(bloques)
            return unir_multimsg([head] + bloques) if bloques else unir_multimsg([head])
        partes = []
        if es_acierto or not tail:
            partes.append(head)
        if tail:
            partes.append(tail)
        return unir_multimsg(partes)
    if es_acierto:
        if head_override:
            return unir_multimsg([head_override, _CTA_LISTO_SIGUIENTE_MATERIAL_EVAL])
        return '[MULTI_MSG]' + mensaje_exito_eval_opciones_con_cta_listo(paso.feedback_correcto)
    # El *listo* ya se pidió junto al feedback del intento incorrecto: entregar siguiente micro(s) sin repetir «Seguimos…».
    modulo_col = progreso.modulo_actual
    if modulo_col:
        return entregar_bloque_secciones_desde_paso(
            progreso, modulo_col, progreso.paso_actual_modulo
        )
    return '[MULTI_MSG]' + mensaje_neutro_avance_eval_con_cta_listo()


# Mensaje al estudiante si modo "pasos" quedó mal configurado (sin filas PasoModulo activas).
FALLBACK_MODULO_PASOS_SIN_PASOS = (
    '📚 Estamos organizando el contenido de esta unidad. '
    'Intentá de nuevo en unos minutos o escribe *listo* para retomar tu curso.'
)


def modulo_usa_pasos(modulo: Optional[Modulo]) -> bool:
    """
    True si el flujo WhatsApp debe usar pasos internos (PasoModulo).
    - modo 'pasos'  → True aunque no haya pasos (el operador debe corregir; ver fallback).
    - modo 'legacy' → False aunque existan pasos en BD
    - modo 'auto'   → True solo si hay al menos un PasoModulo activo
    """
    if not modulo:
        return False
    from .models import Modulo

    modo = getattr(modulo, 'modo_entrega', None) or Modulo.MODO_ENTREGA_AUTO
    if modo == Modulo.MODO_ENTREGA_PASOS:
        return True
    if modo == Modulo.MODO_ENTREGA_LEGACY:
        return False
    return pasos_activos_qs(modulo).exists()


def log_y_mensaje_modo_pasos_sin_pasos(modulo: Modulo, contexto: str) -> str:
    """Log operativo 🔧; devuelve texto seguro para el estudiante."""
    logger.warning(
        '🔧 [pasos] modo_entrega=pasos sin pasos activos | modulo_id=%s ctx=%s',
        modulo.id,
        contexto,
    )
    return FALLBACK_MODULO_PASOS_SIN_PASOS


def pasos_activos_qs(modulo: Modulo):
    from .models import PasoModulo

    return (
        PasoModulo.objects.filter(modulo=modulo, activo=True, seccion__activa=True)
        .select_related('seccion')
        .order_by('orden', 'id')
    )


def modulo_tiene_pasos_activos(modulo: Optional[Modulo]) -> bool:
    """True si hay al menos un PasoModulo activo en BD (no usa modo_entrega)."""
    if not modulo:
        return False
    return pasos_activos_qs(modulo).exists()


def cuenta_microcontenidos_modulo(modulo: Optional[Modulo]) -> int:
    """Microcontenidos guardados en BD (cualquier estado activo/inactivo)."""
    if not modulo or not getattr(modulo, 'pk', None):
        return 0
    from .models import PasoModulo

    return PasoModulo.objects.filter(modulo=modulo).count()


def _paso_form_cuenta_como_microcontenido(cleaned_data: dict) -> bool:
    if not cleaned_data or cleaned_data.get('DELETE'):
        return False
    return bool(cleaned_data.get('seccion'))


def _paso_form_marcado_borrar(form) -> bool:
    cd = getattr(form, 'cleaned_data', None) or {}
    if cd.get('DELETE'):
        return True
    data = getattr(form, 'data', None)
    if data is None:
        return False
    return bool(data.get(f'{form.prefix}-DELETE'))


def cuenta_microcontenidos_desde_formset(pasos_formset) -> int:
    """Cuenta pasos válidos en el POST; si el form no limpió, cae al instance guardado."""
    if not pasos_formset:
        return 0
    n = 0
    for form in pasos_formset.forms:
        if _paso_form_marcado_borrar(form):
            continue
        cd = getattr(form, 'cleaned_data', None)
        if cd and _paso_form_cuenta_como_microcontenido(cd):
            n += 1
            continue
        # Form con error / vacío: no borrar lo ya persistido con sección.
        inst = getattr(form, 'instance', None)
        if inst is not None and getattr(inst, 'pk', None) and getattr(inst, 'seccion_id', None):
            n += 1
    return n


def ids_pasos_marcados_borrar(pasos_formset) -> set[int]:
    if not pasos_formset:
        return set()
    out: set[int] = set()
    for form in pasos_formset.forms:
        if not _paso_form_marcado_borrar(form):
            continue
        pk = getattr(getattr(form, 'instance', None), 'pk', None)
        if pk:
            out.add(int(pk))
    return out


def cuenta_microcontenidos_efectivos(modulo: Optional[Modulo], *, pasos_formset=None) -> int:
    """
    Microcontenidos que quedan tras guardar: POST (formset) + fallback BD
    (excluye los marcados para borrar). Evita exigir Modulo.contenido cuando
    ya hay pasos guardados pero el formset no aportó cleaned_data útil.
    """
    if pasos_formset is not None:
        n_form = cuenta_microcontenidos_desde_formset(pasos_formset)
        if n_form > 0:
            return n_form
        if not modulo or not getattr(modulo, 'pk', None):
            return 0
        from .models import PasoModulo

        borrados = ids_pasos_marcados_borrar(pasos_formset)
        qs = PasoModulo.objects.filter(modulo=modulo)
        if borrados:
            qs = qs.exclude(pk__in=borrados)
        return qs.count()
    return cuenta_microcontenidos_modulo(modulo)


def modulo_requiere_contenido_texto(modulo: Optional[Modulo], *, pasos_formset=None) -> bool:
    """True si Modulo.contenido es obligatorio (sin filas de microcontenido)."""
    return cuenta_microcontenidos_efectivos(modulo, pasos_formset=pasos_formset) == 0


def validar_contenido_modulo(
    contenido: str,
    modulo: Optional[Modulo],
    *,
    pasos_formset=None,
) -> None:
    from django.core.exceptions import ValidationError

    if modulo_requiere_contenido_texto(modulo, pasos_formset=pasos_formset):
        if not (contenido or '').strip():
            raise ValidationError(
                'El contenido del módulo es obligatorio cuando no hay microcontenidos configurados.'
            )


def reset_progreso_pasos_modulo(progreso: ProgresoEstudiante, save: bool = True) -> None:
    progreso.paso_actual_modulo = 1
    progreso.esperando_respuesta_evaluacion_paso = False
    progreso.paso_evaluacion_paso = None
    if save:
        progreso.save(
            update_fields=[
                'paso_actual_modulo',
                'esperando_respuesta_evaluacion_paso',
                'paso_evaluacion_paso',
            ]
        )


def _letra_correcta_eval_opciones(paso: PasoModulo) -> str:
    """Letra correcta A–D: prioriza el campo admin, luego opciones_json; no exige dict de textos."""
    rc = (getattr(paso, 'respuesta_correcta', None) or '').strip().upper()[:1]
    if rc in ('A', 'B', 'C', 'D'):
        return rc
    data = paso.opciones_json or {}
    if isinstance(data, dict):
        c = data.get('correcta')
        if c is None:
            c = data.get('respuesta_correcta')
        if c is not None:
            letra = str(c).strip().upper()[:1]
            if letra in ('A', 'B', 'C', 'D'):
                return letra
    return ''


def _opciones_dict(paso: PasoModulo) -> dict[str, str]:
    """Textos A–D: campos del admin y, si faltan letras, claves en opciones_json (cualquier tipo)."""
    out: dict[str, str] = {}
    for letter in ('A', 'B', 'C', 'D'):
        raw = getattr(paso, f'eval_opcion_{letter.lower()}', None) or ''
        v = str(raw).strip()
        if v:
            out[letter] = v
    data = paso.opciones_json or {}
    if isinstance(data, dict):
        for letter in ('A', 'B', 'C', 'D'):
            if letter in out:
                continue
            val = data.get(letter)
            if val is None or not str(val).strip():
                val = data.get(letter.lower())
            if val is not None and str(val).strip():
                out[letter] = str(val).strip()
        for alt_key, letter in (
            ('opcion_a', 'A'),
            ('opcion_b', 'B'),
            ('opcion_c', 'C'),
            ('opcion_d', 'D'),
        ):
            if letter in out:
                continue
            val = data.get(alt_key)
            if val is not None and str(val).strip():
                out[letter] = str(val).strip()
    return out


def paso_contenido_con_mc_como_eval(paso: PasoModulo) -> bool:
    """Contenido configurado como texto pero con A–D + correcta (tipo mal elegido en admin)."""
    from .models import PasoModulo

    if paso.tipo != PasoModulo.TIPO_CONTENIDO:
        return False
    opts = _opciones_dict(paso)
    letra = _letra_correcta_eval_opciones(paso)
    return len(opts) >= 2 and letra in opts


def _split_media_caption_y_rest(contenido: str) -> tuple[str, str]:
    """
    Primera línea o párrafo → caption junto al video; el resto va después del [DELAY].
    Un solo párrafo → caption vacío: todo el texto va en el mismo bloque que [MEDIA:] (ver partes_mensaje_paso).
    """
    t = (contenido or '').strip()
    if not t:
        return '', ''
    if '\n\n' in t:
        first, rest = t.split('\n\n', 1)
        return first.strip(), rest.strip()
    if '\n' in t:
        first, rest = t.split('\n', 1)
        return first.strip(), rest.strip()
    return '', t


def _suffix_evaluacion_paso(paso: PasoModulo) -> str:
    from .models import PasoModulo

    parts: list[str] = []
    if paso.tipo == PasoModulo.TIPO_EVAL_OPC or paso_contenido_con_mc_como_eval(paso):
        opts = _opciones_dict(paso)
        lines = [f"🔹 *{k}*) {opts[k]}" for k in ('A', 'B', 'C', 'D') if k in opts]
        if lines:
            parts.append("\n\n" + "\n".join(lines))
        else:
            logger.warning(
                '📚 [pasos] paso evaluación sin opciones A–D visibles | paso_id=%s tipo=%s',
                paso.id,
                paso.tipo,
            )
        parts.append(
            "\n\n💡 Responde con la letra correcta (*A*, *B*, *C* o *D*), como en la validación del módulo."
        )
    elif paso.tipo == PasoModulo.TIPO_EVAL_ABIERTA:
        parts.append("\n\n✍️ Envía tu respuesta en un mensaje. La facilitadora la calificará.")
    elif paso.tipo in (PasoModulo.TIPO_RETO, PasoModulo.TIPO_ENTREGA):
        parts.append("\n\n📎 Envía tu respuesta o escribe *listo* cuando termines.")
    return ''.join(parts)


def _mensaje_es_solo_avance_listo(texto_crudo: str) -> bool:
    """True si el usuario solo pide avanzar (listo/ok…) sin enviar una letra A–D."""
    raw = (texto_crudo or '').strip().lower().replace('*', '').strip()
    if not raw:
        return False
    if re.fullmatch(r'[a-d]', raw):
        return False
    tokens = [t for t in re.sub(r'[^a-záéíóúüñ\s]', ' ', raw).split() if t]
    if not tokens:
        return False
    gate = {'listo', 'lista', 'ok', 'dale', 'siguiente', 'continuar', 'sigue', 'si', 'sí', 'ya'}
    return set(tokens) <= gate


def _feedback_incorrecto_paso_estilo_mini(paso: PasoModulo, letra_usuario: str) -> str:
    """Mensaje al fallar (estilo mini examen); respeta feedback_incorrecto del admin si existe."""
    custom = (paso.feedback_incorrecto or '').strip()
    if custom:
        return custom
    letra_ok = _letra_correcta_eval_opciones(paso)
    opts = _opciones_dict(paso)
    texto_ok = opts.get(letra_ok, '') if letra_ok else ''
    if letra_ok and texto_ok:
        correcto = f"✅ La respuesta correcta era: *{letra_ok})* {texto_ok}\n\n"
    elif letra_ok:
        correcto = f"✅ La respuesta correcta era la opción *{letra_ok}*.\n\n"
    else:
        correcto = ""
    return (
        f"❌ *Respuesta incorrecta*\n\n"
        f"{correcto}"
        f"🔄 Probá de nuevo: revisá las opciones y enviá solo una letra (*A*, *B*, *C* o *D*)."
    )


def formatear_texto_paso(paso: PasoModulo, curso) -> str:
    """
    Texto que vería el estudiante en un solo mensaje (sin media o para depuración).
    No incluye el título del paso ni el de la sección: son referencia interna en admin.
    """
    body = (paso.contenido or '').strip()
    return (body + _suffix_evaluacion_paso(paso)).strip()


def partes_mensaje_paso(paso: PasoModulo, curso) -> list[str]:
    """
    Bloques para MULTI_MSG.
    Con media: primero adjunto con caption mínimo; el texto del paso (y la evaluación) va después del [DELAY].
    Si el contenido tiene dos párrafos (\\n\\n o \\n), el primero puede ir como caption junto al video.
    """
    url = (paso.media_url or '').strip()
    body = (paso.contenido or '').strip()
    tail = _suffix_evaluacion_paso(paso)
    if not url:
        msg = (body + tail).strip()
        return [msg if msg else '']
    caption, rest = _split_media_caption_y_rest(body)
    if caption:
        bloque_media = parte_mensaje_con_media(url, caption)
        after = (rest + tail).strip()
    elif body:
        bloque_media = parte_mensaje_con_media(url, body)
        after = tail.strip()
    else:
        bloque_media = parte_mensaje_con_media(url, MENSAJE_CAPTION_SOLO_MEDIA)
        after = tail.strip()
    partes: list[str] = [bloque_media, '[DELAY:5]']
    if after:
        partes.append(after)
    return partes


def unir_multimsg(partes: list[str]) -> str:
    return "[MULTI_MSG]" + "[SEP]".join(p for p in partes if p)


def _ids_secciones_activas_ordenadas(modulo: Modulo) -> list[int]:
    from .models import SeccionModulo

    return list(
        SeccionModulo.objects.filter(modulo=modulo, activa=True)
        .order_by('orden', 'id')
        .values_list('id', flat=True)
    )


def _batch_pasos_desde_indice(modulo: Modulo, qs: list, idx: int) -> list:
    """
    idx en 1..len(qs). Por defecto **una sección por cada *listo*** (confirma comprensión entre bloques).

    El campo ``secciones_por_listo`` en admin puede ser >1 por compatibilidad, pero en WhatsApp
    solo tiene sentido pedir *listo* entre secciones; si está en 2..5 se registra en log y se usa 1.

    Dentro de la misma sección se envían todos los pasos consecutivos hasta una evaluación (incluida)
    o hasta el último paso de esa sección. Corta después del primer paso de evaluación incluido.
    Si la evaluación es el **primer** paso de la sección siguiente, se incluye en el mismo lote
    (mismo disparador de *listo*) para que el enunciado y las opciones no se separen.
    """
    if idx < 1 or idx > len(qs):
        return []
    k_raw = getattr(modulo, 'secciones_por_listo', None)
    try:
        k_config = int(k_raw)
    except (TypeError, ValueError):
        k_config = 1
    k_config = max(1, min(k_config, 5))
    k = 1
    if k_config > 1:
        logger.info(
            '📚 [pasos] secciones_por_listo=%s → usando 1 (un *listo* por sección/bloque) | modulo_id=%s',
            k_config,
            modulo.id,
        )
    sec_order = _ids_secciones_activas_ordenadas(modulo)
    start = qs[idx - 1]
    try:
        i0 = sec_order.index(start.seccion_id)
    except ValueError:
        return [start]
    allowed_sec = set(sec_order[i0 : i0 + k])
    batch = []
    for p in qs[idx - 1 :]:
        if p.seccion_id not in allowed_sec:
            break
        batch.append(p)
        if p.es_evaluacion:
            break
    # Evaluación como primer paso de la siguiente sección: mismo envío que el bloque actual
    # (si no, solo salía el enunciado y el CTA de *listo* sin opciones A–D).
    if batch and not batch[-1].es_evaluacion:
        try:
            pos = qs.index(batch[-1])
        except ValueError:
            pos = -1
        if 0 <= pos < len(qs) - 1:
            nxt = qs[pos + 1]
            if nxt.es_evaluacion:
                batch.append(nxt)
    return batch


def _urls_y_captions_multimedia_modulo(modulo: Modulo) -> list[tuple[str, str | None]]:
    """Lista (url, caption_opcional) de ArchivoModulo / video del módulo."""
    from .response_templates import obtener_video_url

    items: list[tuple[str, str | None]] = []
    try:
        archivos = list(modulo.archivos_multimedia.filter(activo=True))
    except Exception:
        archivos = []
    iconos = {
        'video': '🎥',
        'imagen': '🖼️',
        'infografia': '📊',
        'pdf': '📄',
        'audio': '🎵',
    }
    urls_vistas: set[str] = set()
    for archivo in archivos:
        try:
            url = (archivo.get_url_para_envio() or '').strip()
        except Exception:
            url = ''
        if not url or url in urls_vistas:
            continue
        urls_vistas.add(url)
        icono = iconos.get(getattr(archivo, 'tipo', ''), '📁')
        titulo = (getattr(archivo, 'titulo', None) or '').strip()
        cap = f'{icono} {titulo}'.strip() if titulo else None
        items.append((url, cap))
    if not items:
        try:
            video_url = (obtener_video_url(modulo) or '').strip()
        except Exception:
            video_url = ''
        if video_url and video_url not in urls_vistas:
            items.append((video_url, None))
    return items


def partes_multimedia_modulo(modulo: Modulo) -> list[str]:
    """
    Adjuntos de la pestaña Multimedia / video del módulo (ArchivoModulo).
    En modo pasos estos archivos se ignoraban antes; se reinyectan al abrir el módulo.
    """
    partes: list[str] = []
    for url, cap in _urls_y_captions_multimedia_modulo(modulo):
        partes.append(parte_mensaje_con_media(url, cap))
    if partes:
        partes.append('[DELAY:5]')
        logger.info(
            '📎 [pasos] multimedia de módulo reinyectada | modulo_id=%s n=%s',
            getattr(modulo, 'id', None),
            len(partes) - 1,
        )
    return partes


def _fusionar_multimedia_con_primer_paso(
    multi_items: list[tuple[str, str | None]],
    batch: list,
    curso,
) -> tuple[list[str], list]:
    """
    Evita: burbuja genérica «Aquí tiene el material…» + misma idea del micro aparte.
    Si el primer paso de contenido no trae media propia, su texto va como caption
    del primer ArchivoModulo; el resto de archivos sigue con su caption.
    """
    from .models import PasoModulo

    if not multi_items or not batch:
        partes = [parte_mensaje_con_media(u, c) for u, c in multi_items]
        if partes:
            partes.append('[DELAY:5]')
        return partes, batch

    first = batch[0]
    body = (first.contenido or '').strip()
    tiene_media_propia = bool((first.media_url or '').strip())
    es_contenido = first.tipo == PasoModulo.TIPO_CONTENIDO and not paso_contenido_con_mc_como_eval(first)

    if not (es_contenido and body and not tiene_media_propia):
        partes = [parte_mensaje_con_media(u, c) for u, c in multi_items]
        if partes:
            partes.append('[DELAY:5]')
        return partes, batch

    url0, _cap0 = multi_items[0]
    # Caption = texto del micro (WhatsApp limita; se corta con margen)
    caption = body if len(body) <= 900 else (body[:897].rstrip() + '…')
    partes: list[str] = [parte_mensaje_con_media(url0, caption)]
    for url, cap in multi_items[1:]:
        partes.append(parte_mensaje_con_media(url, cap))
    partes.append('[DELAY:5]')
    logger.info(
        '📎 [pasos] multimedia fusionada con primer micro | paso_id=%s url=%s',
        getattr(first, 'id', None),
        url0[:80],
    )
    # Primer paso ya va en el caption: no volver a mandar su texto suelto
    return partes, batch[1:]


def entregar_bloque_secciones_desde_paso(
    progreso: ProgresoEstudiante, modulo: Modulo, idx: int
) -> str:
    """Entrega **una sección (bloque) por cada *listo***; dentro de la sección, todos los pasos hasta evaluación."""
    qs = list(pasos_activos_qs(modulo))
    n = len(qs)
    batch_orig = _batch_pasos_desde_indice(modulo, qs, idx)
    if not batch_orig:
        raise ValueError('índice de paso fuera de rango o batch vacío')
    curso = progreso.curso
    partes: list[str] = []
    batch_envio = list(batch_orig)
    # Al abrir el módulo (primer índice), adjuntar Multimedia (fusionada al 1.er micro si aplica).
    if idx == 1:
        multi_items = _urls_y_captions_multimedia_modulo(modulo)
        multi_partes, batch_envio = _fusionar_multimedia_con_primer_paso(
            multi_items, batch_envio, curso
        )
        partes.extend(multi_partes)
    last_sec_id = None
    for paso in batch_envio:
        if paso.seccion_id != last_sec_id:
            if last_sec_id is not None:
                partes.append('[DELAY:2]')
            last_sec_id = paso.seccion_id
        n_opts = len(_opciones_dict(paso))
        logger.info(
            '📚 [pasos] armando micro | paso_id=%s tipo=%s n_opciones=%s tiene_media=%s contenido_len=%s',
            paso.id,
            paso.tipo,
            n_opts,
            bool((paso.media_url or '').strip()),
            len((paso.contenido or '').strip()),
        )
        partes.extend(partes_mensaje_paso(paso, curso))
    last_paso = batch_orig[-1]
    last_idx = qs.index(last_paso) + 1

    if last_paso.es_evaluacion:
        progreso.esperando_respuesta_evaluacion_paso = True
        progreso.paso_evaluacion_paso = last_paso
        progreso.paso_actual_modulo = last_idx
        progreso.save(
            update_fields=[
                'esperando_respuesta_evaluacion_paso',
                'paso_evaluacion_paso',
                'paso_actual_modulo',
            ]
        )
        logger.info(
            "📚 [pasos] evaluación paso (bloque) | estudiante_id=%s progreso_id=%s paso_id=%s idx=%s",
            progreso.estudiante_id,
            progreso.id,
            last_paso.id,
            last_idx,
        )
    else:
        progreso.paso_actual_modulo = last_idx + 1
        progreso.esperando_respuesta_evaluacion_paso = False
        progreso.paso_evaluacion_paso = None
        progreso.save(
            update_fields=[
                'paso_actual_modulo',
                'esperando_respuesta_evaluacion_paso',
                'paso_evaluacion_paso',
            ]
        )
        if progreso.paso_actual_modulo <= n:
            sig_idx = progreso.paso_actual_modulo
            siguiente_es_eval = False
            if 1 <= sig_idx <= len(qs):
                siguiente_es_eval = qs[sig_idx - 1].es_evaluacion
            otro_bloque = False
            if 1 <= sig_idx <= len(qs):
                try:
                    sec_cerrada = batch_orig[-1].seccion_id
                    next_sec_id = qs[sig_idx - 1].seccion_id
                    otro_bloque = bool(
                        sec_cerrada and next_sec_id and next_sec_id != sec_cerrada
                    )
                except (IndexError, AttributeError):
                    otro_bloque = False
            if siguiente_es_eval:
                p_ev = qs[sig_idx - 1]
                partes.extend(partes_mensaje_paso(p_ev, curso))
                progreso.esperando_respuesta_evaluacion_paso = True
                progreso.paso_evaluacion_paso = p_ev
                progreso.paso_actual_modulo = sig_idx
                progreso.save(
                    update_fields=[
                        'esperando_respuesta_evaluacion_paso',
                        'paso_evaluacion_paso',
                        'paso_actual_modulo',
                    ]
                )
                logger.warning(
                    '📚 [pasos] recuperación: evaluación incluida en el mismo envío '
                    '(hueco entre secciones) | paso_id=%s sig_idx=%s',
                    p_ev.id,
                    sig_idx,
                )
            elif otro_bloque:
                partes.append(MSG_LISTO_ABRIR_SIGUIENTE_BLOQUE)
            else:
                partes.append(MSG_LISTO_CONTINUAR_EN_MODULO)
        else:
            from .avance_whatsapp import CTX_FIN_ENTREGA_MODULO, resolver_cta_listo

            partes.append(
                resolver_cta_listo(progreso.estudiante, progreso.curso, CTX_FIN_ENTREGA_MODULO)
            )
        logger.info(
            "📚 [pasos] bloque entregado (1 sección por *listo*) | estudiante_id=%s progreso_id=%s "
            "último_paso_id=%s nuevo_idx=%s n_pasos=%s sec_cerrada_ids=%s",
            progreso.estudiante_id,
            progreso.id,
            last_paso.id,
            progreso.paso_actual_modulo,
            n,
            sorted({p.seccion_id for p in batch_orig if p.seccion_id}),
        )

    # Telemetría Centro de Éxito (no debe romper la entrega).
    try:
        from core.models import EstudianteEventoAprendizaje
        from core.telemetria import registrar_evento

        est = progreso.estudiante
        if idx == 1:
            registrar_evento(
                tipo=EstudianteEventoAprendizaje.TIPO_MODULO_INICIADO,
                estudiante=est,
                curso=curso,
                modulo=modulo,
                metadata={'idx': 1},
            )
        for paso in batch_orig:
            media = (paso.media_url or '').strip()
            registrar_evento(
                tipo=EstudianteEventoAprendizaje.TIPO_CONTENIDO_ENVIADO,
                estudiante=est,
                curso=curso,
                modulo=modulo,
                paso=paso,
                seccion=paso.seccion if paso.seccion_id else None,
                metadata={
                    'paso_tipo': paso.tipo,
                    'paso_orden': paso.orden,
                    'tiene_media': bool(media),
                    'media_url': media[:500] if media else '',
                },
            )
    except Exception as exc:
        logger.warning('telemetria entregar_bloque: %s', exc)

    return unir_multimsg(partes)


def entregar_paso_indice(progreso: ProgresoEstudiante, modulo: Modulo, idx: int) -> str:
    """Entrega el paso en posición idx (1-based) y actualiza progreso."""
    from .models import PasoModulo

    qs = list(pasos_activos_qs(modulo))
    n = len(qs)
    if idx < 1 or idx > n:
        raise ValueError('índice de paso fuera de rango')
    paso = qs[idx - 1]
    curso = progreso.curso
    partes = partes_mensaje_paso(paso, curso)
    if paso.es_evaluacion:
        progreso.paso_actual_modulo = idx
        progreso.esperando_respuesta_evaluacion_paso = True
        progreso.paso_evaluacion_paso = paso
        progreso.save(
            update_fields=[
                'paso_actual_modulo',
                'esperando_respuesta_evaluacion_paso',
                'paso_evaluacion_paso',
            ]
        )
        logger.info(
            "📚 [pasos] evaluación paso | estudiante_id=%s progreso_id=%s paso_id=%s idx=%s",
            progreso.estudiante_id,
            progreso.id,
            paso.id,
            idx,
        )
    else:
        progreso.paso_actual_modulo = idx + 1
        progreso.esperando_respuesta_evaluacion_paso = False
        progreso.paso_evaluacion_paso = None
        progreso.save(
            update_fields=[
                'paso_actual_modulo',
                'esperando_respuesta_evaluacion_paso',
                'paso_evaluacion_paso',
            ]
        )
        if progreso.paso_actual_modulo <= n:
            partes.append(MSG_LISTO_CONTINUAR_EN_MODULO)
        else:
            from .avance_whatsapp import CTX_FIN_ENTREGA_MODULO, resolver_cta_listo

            partes.append(
                resolver_cta_listo(progreso.estudiante, progreso.curso, CTX_FIN_ENTREGA_MODULO)
            )
        logger.info(
            "📚 [pasos] contenido entregado | estudiante_id=%s progreso_id=%s paso_id=%s nuevo_idx=%s",
            progreso.estudiante_id,
            progreso.id,
            paso.id,
            progreso.paso_actual_modulo,
        )
    return unir_multimsg(partes)


def mensaje_recordatorio_paso_actual(progreso: ProgresoEstudiante, modulo: Modulo) -> Optional[str]:
    """
    Nudge sin reenviar el microcompleto (evita duplicar texto + infografía al *listo*).
    Si hay evaluación pendiente, sí reenvía el enunciado/opciones.
    """
    qs = list(pasos_activos_qs(modulo))
    n = len(qs)
    if n == 0:
        return None
    if progreso.esperando_respuesta_evaluacion_paso and progreso.paso_evaluacion_paso_id:
        partes = partes_mensaje_paso(progreso.paso_evaluacion_paso, progreso.curso)
        partes.append(
            "Cuando puedas, responde según las opciones de arriba 👆 "
            "(letra o mensaje según el tipo de actividad)."
        )
        return unir_multimsg(partes)

    idx = progreso.paso_actual_modulo
    if idx > n:
        return None
    if idx < 1:
        idx = 1
    # No reenviar contenido: el alumno ya lo tiene; solo recordar el CTA.
    return (
        "Sigues en este material. Cuando termines de revisarlo, escribe *listo* "
        "para continuar 👇"
    )


def _evaluar_abierta_microcontenido_facilitadora(
    estudiante: Estudiante,
    progreso: ProgresoEstudiante,
    paso: PasoModulo,
    respuesta_texto: str,
) -> tuple[object, str, str]:
    """
    Califica evaluación abierta de microcontenido con la misma IA facilitadora
    que la pregunta final del curso. Devuelve (puntaje_o_nota, feedback, sufijo_puntos).
    """
    from .tutor_ia_modulo import evaluar_reto_facilitador
    from core.gamificacion_modo import (
        formatear_nota,
        gamificacion_otorga_puntos,
        get_modo_gamificacion,
        modo_usa_calificacion,
        registrar_nota_gamificacion,
        resumen_calificaciones_estudiante,
    )

    modulo = progreso.modulo_actual
    curso = progreso.curso
    modulos_eval = [modulo] if modulo else []
    enunciado = (paso.contenido or '').strip() or 'Pregunta abierta del módulo'
    puntaje = 7
    feedback = (
        '1. Gracias por su respuesta; usted plantea una línea de acción.\n\n'
        '2. Para subir nivel, puede ser más preciso en diagnóstico y acción concreta.\n\n'
        '3. Puntaje total: 7/10'
    )
    puntos_msg = ''

    try:
        modo_gami = get_modo_gamificacion(getattr(estudiante, 'cliente', None))
        puntaje, feedback = evaluar_reto_facilitador(
            modulos_eval,
            respuesta_texto,
            enunciado,
            estudiante_nombre=estudiante.nombre or 'Estudiante',
            curso_nombre=getattr(curso, 'nombre', None),
            modo_gamificacion=modo_gami,
        )
        if modo_usa_calificacion(getattr(estudiante, 'cliente', None)):
            nota_f = float(puntaje)
            registrar_nota_gamificacion(
                estudiante,
                nota_f,
                'reto',
                curso=curso,
                modulo=modulo,
                detalle=f'Evaluación abierta (paso {paso.orden})',
            )
            res_n = resumen_calificaciones_estudiante(
                estudiante,
                curso.id if curso else None,
            )
            prom = res_n.get('promedio')
            extra_prom = (
                f"\n📊 *Promedio acumulado:* {formatear_nota(prom)}/5"
                if prom is not None else ''
            )
            puntos_msg = f"\n\n📋 *Nota:* {formatear_nota(nota_f)}/5{extra_prom}"
        elif gamificacion_otorga_puntos(getattr(estudiante, 'cliente', None), curso):
            from .gamificacion import PerfilGamificacion

            perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
            puntaje_10 = int(puntaje)
            puntos = int(max(1, min(10, puntaje_10)) * 5)
            perfil.agregar_puntos(
                puntos,
                f'Evaluación abierta paso {paso.orden}: {puntaje_10}/10',
            )
            perfil.refresh_from_db()
            puntos_msg = f"\n\n💰 *+{puntos} puntos* → Total: *{perfil.puntos_totales} pts*"
    except Exception as exc:
        logger.warning('[pasos] eval abierta facilitadora falló: %s', exc)

    return puntaje, feedback, puntos_msg


def procesar_respuesta_evaluacion_paso(
    estudiante: Estudiante,
    progreso: ProgresoEstudiante,
    texto_crudo: str,
) -> Optional[str]:
    """
    Si está esperando evaluación de paso, evalúa y devuelve MULTI_MSG o str.
    Si no aplica, devuelve None.
    """
    if not progreso.esperando_respuesta_evaluacion_paso or not progreso.paso_evaluacion_paso_id:
        return None
    paso = progreso.paso_evaluacion_paso
    modulo = progreso.modulo_actual
    if not modulo or paso.modulo_id != modulo.id:
        logger.warning(
            "⚠️ [pasos] paso eval fuera de módulo actual | est=%s progreso=%s",
            estudiante.id,
            progreso.id,
        )
        progreso.esperando_respuesta_evaluacion_paso = False
        progreso.paso_evaluacion_paso = None
        progreso.save(
            update_fields=[
                'esperando_respuesta_evaluacion_paso',
                'paso_evaluacion_paso',
            ]
        )
        return None

    from .models import PasoModulo

    texto = (texto_crudo or '').strip()
    logger.info(
        '📚 [pasos] intento evaluación | est=%s paso_id=%s tipo=%s n_op=%s preview=%r',
        estudiante.id,
        paso.id,
        paso.tipo,
        len(_opciones_dict(paso)),
        (texto_crudo or '')[:160],
    )
    idx = progreso.paso_actual_modulo
    qs = list(pasos_activos_qs(modulo))
    n = len(qs)

    ok = False
    letra_in_eval = ''
    head_facilitadora = None
    if paso.tipo == PasoModulo.TIPO_EVAL_OPC or paso_contenido_con_mc_como_eval(paso):
        letra_in_eval = re.sub(r'[^a-dA-D]', '', texto)
        letra_in_eval = (letra_in_eval[:1] or '').upper()
        if not letra_in_eval and _mensaje_es_solo_avance_listo(texto_crudo):
            progreso.esperando_respuesta_evaluacion_paso = False
            progreso.paso_evaluacion_paso = None
            progreso.paso_actual_modulo = idx + 1
            progreso.save(
                update_fields=[
                    'esperando_respuesta_evaluacion_paso',
                    'paso_evaluacion_paso',
                    'paso_actual_modulo',
                ]
            )
            logger.info(
                '📚 [pasos] eval opción múltiple — avance con listo sin letra | est=%s paso_id=%s nuevo_idx=%s',
                estudiante.id,
                paso.id,
                progreso.paso_actual_modulo,
            )
            return _respuesta_cola_tras_avanzar_eval_opc(
                estudiante, progreso, paso, n, es_acierto=False
            )
        letra_ok = _letra_correcta_eval_opciones(paso)
        if not letra_ok:
            logger.error(
                '📚 [pasos] evaluación sin letra correcta (admin) | paso_id=%s',
                paso.id,
            )
            return (
                "⚠️ Esta pregunta no está bien configurada. "
                "Escribí *ayuda* para contactar a soporte."
            )
        ok = bool(letra_in_eval) and letra_in_eval == letra_ok
    elif paso.tipo == PasoModulo.TIPO_EVAL_ABIERTA:
        if texto:
            ok = True
            _puntaje, feedback_ia, puntos_msg = _evaluar_abierta_microcontenido_facilitadora(
                estudiante, progreso, paso, texto,
            )
            head_facilitadora = f"📋 *Facilitadora*\n\n{feedback_ia}{puntos_msg}"
        else:
            ok = False
    elif paso.tipo in (PasoModulo.TIPO_RETO, PasoModulo.TIPO_ENTREGA):
        raw = (texto_crudo or '').strip().lower()
        ok = bool(texto) or raw in ('listo', 'lista', 'ok', 'sí', 'si')
    else:
        ok = bool(texto)

    if not ok:
        if paso.tipo == PasoModulo.TIPO_EVAL_OPC or paso_contenido_con_mc_como_eval(paso):
            fb = _feedback_incorrecto_paso_estilo_mini(paso, letra_in_eval)
            logger.info(
                "📚 [pasos] eval incorrecta | est=%s paso_id=%s",
                estudiante.id,
                paso.id,
            )
            return '[MULTI_MSG]' + mensaje_incorrecto_eval_opciones_con_cta_listo(fb)
        fb = (paso.feedback_incorrecto or '').strip() or (
            "❌ Escriba su respuesta para que la facilitadora pueda calificarla."
        )
        logger.info(
            "📚 [pasos] eval incorrecta | est=%s paso_id=%s",
            estudiante.id,
            paso.id,
        )
        return fb

    progreso.esperando_respuesta_evaluacion_paso = False
    progreso.paso_evaluacion_paso = None
    progreso.paso_actual_modulo = idx + 1
    progreso.save(
        update_fields=[
            'esperando_respuesta_evaluacion_paso',
            'paso_evaluacion_paso',
            'paso_actual_modulo',
        ]
    )
    logger.info(
        "📚 [pasos] eval correcta | est=%s paso_id=%s nuevo_idx=%s n_pasos=%s",
        estudiante.id,
        paso.id,
        progreso.paso_actual_modulo,
        n,
    )

    try:
        from core.models import EstudianteEventoAprendizaje
        from core.telemetria import registrar_evento

        registrar_evento(
            tipo=EstudianteEventoAprendizaje.TIPO_EVALUACION_RESPONDIDA,
            estudiante=estudiante,
            curso=progreso.curso,
            modulo=modulo,
            paso=paso,
            metadata={
                'acierto': True,
                'paso_tipo': paso.tipo,
                'letra': letra_in_eval or '',
            },
        )
    except Exception as exc:
        logger.warning('telemetria eval correcta: %s', exc)

    return _respuesta_cola_tras_avanzar_eval_opc(
        estudiante, progreso, paso, n, es_acierto=True, head_override=head_facilitadora,
    )
