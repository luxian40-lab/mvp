"""Orquestador y helpers del webhook Nat / bot comercial.

Extraido de core.views para reducir el monolito. Las vistas re-exportan
estas funciones para no romper imports existentes.
"""
from __future__ import annotations

import logging
import os
import re
import tempfile
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

from core.models import Cliente, WhatsappLog
from core.utils import enviar_whatsapp_twilio


def _registrar_estado_twilio_callback(post_data):
    from core.views import _registrar_estado_twilio_callback as _impl
    return _impl(post_data)


def _transcribir_audio_twilio(media_url, media_type='audio/ogg'):
    from core.views import _transcribir_audio_twilio as _impl
    return _impl(media_url, media_type=media_type)

def _bot_comercial_sin_contexto_natural(pregunta: str, cliente=None) -> str:
    """Respuestas cuando aún no hay contexto RAG suficiente (tono formal agrónomo)."""
    from core.nati import obtener_nombre_bot

    nombre = obtener_nombre_bot(cliente)
    q = (pregunta or '').strip().lower()

    saludos = {'hola', 'buenas', 'buenos dias', 'buen día', 'buenas tardes', 'buenas noches', 'hey'}
    if q in saludos or any(s in q for s in ['hola', 'buenas', 'buen dia', 'buen día']):
        return (
            f"Buenos días. Soy {nombre}, agrónoma virtual de eki.\n\n"
            "Le acompaño en manejo técnico de su cultivo y, si usted lo solicita, "
            "en orientación de catálogo con base en información oficial.\n\n"
            "Indíqueme, por favor, su cultivo y qué necesita resolver."
        )

    if 'gulupa' in q or 'gulupa' in q:
        return (
            "Perfecto, trabajemos *gulupa*.\n\n"
            "Puedo orientarle en suelo, pH, altitud, nutrición y manejo sanitario "
            "con la información técnica disponible.\n\n"
            "Para una respuesta precisa, indíqueme el punto puntual que desea resolver primero."
        )

    return (
        "Entendido. Vamos a resolverlo de forma técnica y práctica.\n\n"
        "Indíqueme cultivo y objetivo puntual (suelo, nutrición, plaga o enfermedad) "
        "y le responderé con base en la información oficial disponible."
    )


def _extraer_texto_archivo_simple(ruta_archivo: str, *, xlsx_max_rows=None) -> str:
    """Extracción liviana de texto para fallback cuando RAG vectorial no retorna contexto.

    xlsx_max_rows: en Excel limita filas extraídas (evita bloquear Gunicorn con hojas enormes).
    """
    import os

    ext = os.path.splitext(ruta_archivo)[1].lower()
    try:
        if ext == '.txt':
            with open(ruta_archivo, 'r', encoding='utf-8', errors='ignore') as f:
                t = f.read()
                return t[:120000]
        if ext == '.pdf':
            from PyPDF2 import PdfReader

            reader = PdfReader(ruta_archivo)
            parts = []
            for i, p in enumerate(reader.pages):
                if i >= 45:
                    break
                parts.append(p.extract_text() or "")
            return "\n".join(parts)[:120000]
        if ext == '.docx':
            from docx import Document

            doc = Document(ruta_archivo)
            return "\n".join(p.text for p in doc.paragraphs)[:80000]
        if ext in ('.xlsx', '.xlsm'):
            from core.rag_eki_multitenant import RAGClienteCurso

            mr = xlsx_max_rows if xlsx_max_rows is not None else None
            return (RAGClienteCurso._extraer_xlsx(ruta_archivo, max_rows=mr) or '').strip()[:120000]
    except Exception:
        return ""
    return ""


def _contexto_fallback_desde_documentos(
    cliente_ids: list,
    pregunta: str,
    max_chars: int = 1800,
    *,
    max_docs: int = 8,
    xlsx_max_rows: int | None = 3200,
) -> str:
    """Fallback semántico simple sobre documentos indexados para evitar respuestas vacías."""
    from django.db.models import Q
    from core.models import DocumentoRAGComercial
    import re

    tokens = [t for t in re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]{3,}", (pregunta or '').lower())][:12]

    p_q = (pregunta or '').lower()
    consulta_catalogo = bool(
        re.search(
            r'precio|precios|cotiz|lista|tarifa|valor|cu[aá]nto|cuesta|insumo|producto|'
            r'cat[aá]logo|bulto|arroba|\bkg\b|kilo|dosis|paquete|mezcla|fertil|herbic|fungic',
            p_q,
        )
    )

    base_qs = DocumentoRAGComercial.objects.filter(estado='indexado').filter(
        Q(cliente_id__in=cliente_ids) | Q(cliente__isnull=True)
    )
    if consulta_catalogo:
        from django.db.models import Case, IntegerField, When

        qs = base_qs.annotate(
            _catprio=Case(
                When(cliente__isnull=True, then=0),
                default=1,
                output_field=IntegerField(),
            )
        ).order_by('_catprio', '-fecha_indexado', '-fecha_subida')[: max(4, max_docs + 4)]
    else:
        qs = base_qs.order_by('-fecha_indexado', '-fecha_subida')[: max(4, max_docs + 2)]

    fragmentos = []
    chars_total = 0
    docs_procesados = 0
    ya_extracto_general = False
    for doc in qs:
        if docs_procesados >= max_docs:
            break
        try:
            ruta = doc.archivo.path
        except Exception:
            ruta = doc._descargar_temp()
        if not ruta:
            continue

        texto = _extraer_texto_archivo_simple(ruta, xlsx_max_rows=xlsx_max_rows)
        docs_procesados += 1
        if not texto:
            continue

        texto_norm = texto.lower()
        score = sum(1 for tk in tokens if tk in texto_norm)
        usar_extracto_inicial = (
            consulta_catalogo
            and doc.cliente_id is None
            and score <= 0
            and not ya_extracto_general
        )
        if score <= 0 and tokens and not usar_extracto_inicial:
            continue

        pos = 0
        if score > 0:
            for tk in tokens:
                p = texto_norm.find(tk)
                if p >= 0:
                    pos = p
                    break
        if usar_extracto_inicial:
            ini, fin = 0, min(len(texto), 1600)
            ya_extracto_general = True
        else:
            ini = max(0, pos - 260)
            fin = min(len(texto), pos + 640)
        snippet = texto[ini:fin].strip().replace('\x00', ' ')
        if not snippet:
            continue

        bloque = f"[Fuente: {doc.nombre}]\n{snippet}"
        if chars_total + len(bloque) > max_chars:
            break
        fragmentos.append(bloque)
        chars_total += len(bloque)

    if not fragmentos:
        return ""

    return (
        "\n\n📚 CONTEXTO DOCUMENTAL (fallback por archivo indexado):\n"
        + "\n---\n".join(fragmentos)
        + "\n\n⚠️ Usa esta información como base técnica prioritaria."
    )


def _normalizar_consulta_web(pregunta: str) -> str:
    """Normaliza consulta para búsquedas web/académicas de respaldo."""
    import re

    tokens = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ0-9]{3,}", (pregunta or '').lower())
    stop = {
        'para', 'como', 'donde', 'cuando', 'cuanto', 'cuantos', 'cual', 'cuales',
        'tengo', 'necesito', 'quiero', 'sobre', 'desde', 'hasta', 'entre', 'esta',
        'este', 'estos', 'estas', 'porque', 'favor', 'hola', 'buenas', 'dias',
        'tarde', 'noche', 'gracias', 'cultivo', 'agricola', 'agricultura',
    }
    claves = [t for t in tokens if t not in stop]
    if not claves:
        return (pregunta or '').strip()[:120]
    return ' '.join(claves[:10]).strip()


def _contexto_fallback_web_agro(pregunta: str, max_chars: int = 1800) -> str:
    """Busca referencias externas cuando aún no hay contexto RAG suficiente."""
    if not bool(getattr(settings, 'BOT_COMERCIAL_WEB_FALLBACK_ENABLED', True)):
        return ""

    try:
        timeout = float(getattr(settings, 'BOT_COMERCIAL_WEB_FALLBACK_TIMEOUT', 6.0) or 6.0)
    except Exception:
        timeout = 6.0
    try:
        max_fuentes = int(getattr(settings, 'BOT_COMERCIAL_WEB_FALLBACK_MAX_FUENTES', 4) or 4)
    except Exception:
        max_fuentes = 4

    query_base = _normalizar_consulta_web(pregunta)
    if not query_base:
        return ""

    import re
    from html import unescape
    from urllib.parse import quote_plus

    fuentes = []
    vistos = set()

    # 1) Base académica abierta (Crossref) como aproximación a literatura técnica.
    try:
        r = requests.get(
            'https://api.crossref.org/works',
            params={
                'query': query_base,
                'rows': max_fuentes,
                'sort': 'relevance',
                'order': 'desc',
                'select': 'title,container-title,published-print,published-online,created,DOI,URL,abstract',
            },
            timeout=timeout,
            headers={'User-Agent': 'eki-bot-comercial/1.0'},
        )
        r.raise_for_status()
        payload = r.json() or {}
        for item in (payload.get('message') or {}).get('items', [])[:max_fuentes]:
            titulo = ((item.get('title') or [''])[0] or '').strip()
            if not titulo:
                continue

            anio = ''
            for k in ['published-print', 'published-online', 'created']:
                dp = ((item.get(k) or {}).get('date-parts') or [])
                if dp and dp[0]:
                    anio = str(dp[0][0])
                    break

            revista = ((item.get('container-title') or [''])[0] or '').strip()
            doi = (item.get('DOI') or '').strip()
            url = (item.get('URL') or '').strip()
            resumen = re.sub(r'<[^>]+>', ' ', unescape((item.get('abstract') or '').strip()))
            resumen = re.sub(r'\s+', ' ', resumen).strip()[:280]

            clave = (titulo.lower(), url.lower())
            if clave in vistos:
                continue
            vistos.add(clave)

            fuentes.append({
                'origen': 'Academico/Crossref',
                'titulo': titulo,
                'resumen': resumen or f"Referencia técnica {anio or ''} {revista}".strip(),
                'url': url or (f"https://doi.org/{doi}" if doi else ''),
            })
    except Exception as e:
        logger.info("🌐 Fallback académico no disponible: %s", e)

    # 2) Internet general: DuckDuckGo Instant Answer.
    try:
        r = requests.get(
            'https://api.duckduckgo.com/',
            params={
                'q': f"{query_base} manejo agronomico",
                'format': 'json',
                'no_html': 1,
                'skip_disambig': 1,
            },
            timeout=timeout,
            headers={'User-Agent': 'eki-bot-comercial/1.0'},
        )
        r.raise_for_status()
        data = r.json() or {}

        if data.get('AbstractText') and data.get('AbstractURL'):
            titulo_abs = (data.get('Heading') or 'Resumen web técnico').strip()
            clave = (titulo_abs.lower(), (data.get('AbstractURL') or '').lower())
            if clave not in vistos:
                vistos.add(clave)
                fuentes.append({
                    'origen': 'Internet/DuckDuckGo',
                    'titulo': titulo_abs,
                    'resumen': str(data.get('AbstractText') or '').strip()[:280],
                    'url': str(data.get('AbstractURL') or '').strip(),
                })

        def _iter_topics(items):
            for it in items or []:
                if isinstance(it, dict) and 'Text' in it and 'FirstURL' in it:
                    yield it
                for sub in (it.get('Topics') if isinstance(it, dict) else []) or []:
                    if isinstance(sub, dict) and 'Text' in sub and 'FirstURL' in sub:
                        yield sub

        for it in _iter_topics(data.get('RelatedTopics')):
            titulo = str(it.get('Text') or '').strip()
            url = str(it.get('FirstURL') or '').strip()
            if not titulo or not url:
                continue
            clave = (titulo.lower(), url.lower())
            if clave in vistos:
                continue
            vistos.add(clave)
            fuentes.append({
                'origen': 'Internet/DuckDuckGo',
                'titulo': titulo[:160],
                'resumen': titulo[:280],
                'url': url,
            })
            if len(fuentes) >= max_fuentes * 2:
                break
    except Exception as e:
        logger.info("🌐 Fallback internet no disponible: %s", e)

    # 3) Respaldo Wikipedia ES cuando no hay suficiente info externa.
    if len(fuentes) < max_fuentes:
        try:
            r = requests.get(
                'https://es.wikipedia.org/w/api.php',
                params={
                    'action': 'query',
                    'list': 'search',
                    'srsearch': f"{query_base} agricultura",
                    'srlimit': max_fuentes,
                    'format': 'json',
                    'utf8': 1,
                },
                timeout=timeout,
                headers={'User-Agent': 'eki-bot-comercial/1.0'},
            )
            r.raise_for_status()
            data = r.json() or {}
            for item in ((data.get('query') or {}).get('search') or []):
                titulo = str(item.get('title') or '').strip()
                snippet = re.sub(r'<[^>]+>', ' ', unescape(str(item.get('snippet') or '')))
                snippet = re.sub(r'\s+', ' ', snippet).strip()[:280]
                if not titulo:
                    continue
                url = f"https://es.wikipedia.org/wiki/{quote_plus(titulo.replace(' ', '_'))}"
                clave = (titulo.lower(), url.lower())
                if clave in vistos:
                    continue
                vistos.add(clave)
                fuentes.append({
                    'origen': 'Internet/Wikipedia',
                    'titulo': titulo,
                    'resumen': snippet or 'Referencia general de agricultura.',
                    'url': url,
                })
                if len(fuentes) >= max_fuentes * 2:
                    break
        except Exception as e:
            logger.info("🌐 Fallback Wikipedia no disponible: %s", e)

    if not fuentes:
        return ""

    bloques = []
    chars_total = 0
    for idx, f in enumerate(fuentes[: max_fuentes * 2], start=1):
        bloque = (
            f"[Fuente externa {idx} | {f['origen']}]\n"
            f"{f['titulo']}\n"
            f"{f['resumen']}\n"
            f"URL: {f['url'] or 'N/D'}"
        )
        if chars_total + len(bloque) > max_chars:
            break
        bloques.append(bloque)
        chars_total += len(bloque)

    if not bloques:
        return ""

    return (
        "\n\n🌐 INFORMACION COMPLEMENTARIA DE WEB (solo si la oficial de eki no alcanza):\n"
        + "\n---\n".join(bloques)
        + "\n\n⚠️ Si hay información oficial de eki, esa SIEMPRE tiene prioridad sobre estas fuentes externas."
    )


def _bot_comercial_respuesta_catalogo(
    pregunta: str,
    contexto_rag: str,
    diagnostico_vision: str = '',
    contexto_web: str = '',
    historial_chat: str = '',
    cliente=None,
    sesion_comercial=None,
    bloque_contexto_agro: str = '',
    routing=None,
    rag_chunks=None,
    ctx_agro=None,
) -> str:
    """Genera respuesta técnica/comercial estricta basada en contexto RAG (sin alucinaciones).

    Si se pasa `cliente` (instancia de `core.Cliente`), se usa su `system_prompt_extra`
    y `nombre_bot` para personalizar la identidad de Nat.
    """
    api_key = getattr(settings, 'OPENAI_API_KEY', '')
    contexto_base = contexto_rag or contexto_web
    tiene_rag = bool(contexto_rag)
    if not api_key:
        if not contexto_base:
            return _bot_comercial_sin_contexto_natural(pregunta, cliente=cliente)

        if tiene_rag:
            encabezado = "Con base en la información oficial de eki:"
            cierre = "Si aplica cotización, compárteme cantidad, municipio y cultivo."
        else:
            encabezado = (
                "Aún no tengo información oficial de eki suficiente para resolver eso. "
                "Le comparto un respaldo técnico general:"
            )
            cierre = (
                "Si ya tiene ficha técnica o precios del producto, le pido que los hagamos "
                "llegar al equipo de eki para darle una recomendación exacta por cultivo y necesidad."
            )

        return (
            f"{encabezado}\n\n"
            f"{contexto_base[:1200]}\n\n"
            f"{cierre}"
        )

    try:
        from openai import OpenAI
        from core.nati import armar_instruccion_modo, armar_messages_para_openai, armar_system_prompt
        from core.nat_router import decidir_routing_nat
        import time
        inicio = time.time()
        client = OpenAI(api_key=api_key)

        if routing is None:
            routing = decidir_routing_nat(
                pregunta,
                rag_chunks=rag_chunks or [],
                tiene_rag_texto=bool(contexto_rag),
                contexto_rag_chars=len(contexto_rag or ''),
                ctx_agro=ctx_agro,
                diagnostico_vision=diagnostico_vision,
            )

        system_prompt = armar_system_prompt(cliente=cliente)
        bloque_agro = (bloque_contexto_agro or '').strip()
        bloque_ctx_prompt = (
            f"CONTEXTO AGRONÓMICO DEL PRODUCTOR (estructurado):\n{bloque_agro}\n\n"
            if bloque_agro else ''
        )
        try:
            from core.clima_open_meteo import obtener_bloque_clima_para_nat

            bloque_clima = obtener_bloque_clima_para_nat(
                pregunta=pregunta,
                ctx_agro=ctx_agro,
            )
            if bloque_clima:
                bloque_ctx_prompt += f"{bloque_clima}\n\n"
        except Exception:
            logger.exception('Nat Open-Meteo: error al obtener clima')
        bloque_modo = armar_instruccion_modo(routing.modo, routing.escala_premium)
        bloque_consulta = (
            f"CONSULTA DEL PRODUCTOR:\n{pregunta}\n\n"
            f"{bloque_ctx_prompt}"
            f"{bloque_modo}"
            f"DIAGNÓSTICO VISIÓN (si aplica):\n{diagnostico_vision or 'N/A'}\n\n"
            f"INFORMACIÓN OFICIAL DE EKI (fuente principal — use esto con precisión):\n{contexto_rag or '[VACIO]'}\n\n"
            f"INFORMACIÓN COMPLEMENTARIA WEB (solo si la oficial no alcanza):\n{contexto_web or '[VACIO]'}\n\n"
            "Recuerde: nunca mencione al productor términos como RAG, base de "
            "conocimiento, fragmento o documento indexado. Hable como agrónoma formal de eki (siempre de usted).\n"
            "Si la consulta parece error de tipeo, ofrezca 1–2 interpretaciones plausibles "
            "con '¿Quiso decir...?' antes de conclusiones fuertes.\n"
            "Si INFORMACIÓN OFICIAL incluye listas Excel (producto, precio, dosis), "
            "use solo esas cifras; si no aparecen, no las invente."
        )
        if sesion_comercial is not None:
            # Memoria en SesionComercial; no duplicar WhatsappLog en el prompt.
            messages = armar_messages_para_openai(
                sesion=sesion_comercial,
                nuevo_mensaje=bloque_consulta,
                cliente=cliente,
            )
        else:
            user_prompt = bloque_consulta
            if historial_chat:
                user_prompt = (
                    f"{bloque_consulta}\n\n"
                    f"HISTORIAL RECIENTE (referencia):\n{historial_chat}"
                )
            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ]
        modelo = routing.modelo
        temperatura = 0.1 if routing.escala_premium else 0.15
        try:
            max_out = int(getattr(settings, 'BOT_COMERCIAL_OPENAI_MAX_TOKENS', 650) or 650)
        except (TypeError, ValueError):
            max_out = 650
        max_out = max(400, min(max_out, 1200))
        from core.openai_compat import chat_completion_token_kwargs
        completion = client.chat.completions.create(
            model=modelo,
            messages=messages,
            **chat_completion_token_kwargs(modelo, max_out, temperatura),
        )
        texto = (completion.choices[0].message.content or '').strip()
        if not texto:
            # Segundo intento: effort mínimo si el modelo gastó el cupo en reasoning
            completion = client.chat.completions.create(
                model=modelo,
                messages=messages,
                **chat_completion_token_kwargs(
                    modelo, max(max_out, 900), temperatura, reasoning_effort='minimal',
                ),
            )
            texto = (completion.choices[0].message.content or '').strip()
        latencia_ms = int((time.time() - inicio) * 1000)
        usage = getattr(completion, 'usage', None)
        try:
            from core.eventos_ia import emit_ia_agent_triggered

            emit_ia_agent_triggered(
                cliente=cliente,
                agente='nati',
                mensaje=pregunta,
                respuesta=texto,
                modelo=modelo,
                latencia_ms=latencia_ms,
                tokens_in=getattr(usage, 'prompt_tokens', None) if usage else None,
                tokens_out=getattr(usage, 'completion_tokens', None) if usage else None,
                canal='whatsapp_comercial',
                metadata={
                    'tiene_rag': bool(contexto_rag),
                    'tiene_web': bool(contexto_web),
                    'routing_modo': routing.modo,
                    'routing_razon': routing.razon,
                    'escala_premium': routing.escala_premium,
                    'rag_max_similitud': routing.rag_max_similitud,
                },
            )
        except Exception:
            pass
        return texto or "No logré construir una respuesta válida. Intenta con otra consulta."
    except Exception as e:
        logger.warning(f"⚠️ Bot Comercial LLM fallback: {e}")
        if contexto_rag:
            return (
                "Le comparto lo que encontré en la información oficial de eki:\n\n"
                f"{contexto_rag[:1000]}\n\n"
                "Para cotizar, indíqueme cantidad y municipio."
            )
        if contexto_web:
            return (
                "Aún no tengo suficiente contenido indexado para responder con exactitud. "
                "Encontré estas referencias externas de apoyo:\n\n"
                f"{contexto_web[:1000]}\n\n"
                "Si sube fichas técnicas o precios al equipo eki, podré darle una recomendación directa."
            )
        return _bot_comercial_sin_contexto_natural(pregunta, cliente=cliente)


def _bot_comercial_historial_reciente(telefono: str, max_turnos: int = 6, max_chars: int = 1200) -> str:
    """Construye memoria corta de conversación comercial desde WhatsappLog."""
    if not telefono:
        return ''

    try:
        max_turnos = int(max_turnos or 6)
    except (TypeError, ValueError):
        max_turnos = 6
    max_turnos = max(2, min(max_turnos, 12))

    try:
        max_chars = int(max_chars or 1200)
    except (TypeError, ValueError):
        max_chars = 1200
    max_chars = max(300, min(max_chars, 2500))

    logs = list(
        WhatsappLog.objects.filter(
            telefono=telefono,
            agente_usado='BOT_COMERCIAL',
        )
        .exclude(mensaje__isnull=True)
        .exclude(mensaje='')
        .order_by('-fecha')[: (max_turnos * 3)]
    )

    if not logs:
        return ''

    import re

    lineas = []
    for log in reversed(logs):
        texto = re.sub(r'\s+', ' ', str(log.mensaje or '').strip())
        if not texto:
            continue
        if texto.startswith('[MEDIA:'):
            continue

        if len(texto) > 260:
            texto = f"{texto[:257]}..."

        tipo = str(log.tipo or '').upper()
        rol = 'Cliente' if tipo == 'INCOMING' else 'Bot'
        lineas.append(f"{rol}: {texto}")

    if not lineas:
        return ''

    # Recorta por caracteres conservando las líneas más recientes.
    salida = []
    total = 0
    for linea in reversed(lineas):
        costo = len(linea) + 1
        if total + costo > max_chars:
            break
        salida.append(linea)
        total += costo

    salida.reverse()
    return '\n'.join(salida)


def _obtener_o_crear_sesion_comercial(telefono: str, cliente=None, horas_expira: int = 4):
    from django.utils import timezone as _tz
    from core.models import SesionComercial

    telefono = (telefono or '').strip()
    if not telefono:
        return None
    ahora = _tz.now()
    delta = timedelta(hours=max(1, int(horas_expira or 4)))
    sesion = (
        SesionComercial.objects.filter(telefono=telefono)
        .order_by('-fecha_ultimo_mensaje')
        .first()
    )
    if not sesion:
        return SesionComercial.objects.create(telefono=telefono, cliente=cliente)

    if sesion.fecha_ultimo_mensaje and sesion.fecha_ultimo_mensaje < (ahora - delta):
        sesion.historial_mensajes = []
        sesion.cliente = cliente
        sesion.save(update_fields=['historial_mensajes', 'cliente', 'fecha_ultimo_mensaje'])
    elif cliente and sesion.cliente_id != getattr(cliente, 'id', None):
        sesion.cliente = cliente
        sesion.save(update_fields=['cliente', 'fecha_ultimo_mensaje'])
    return sesion


def _actualizar_sesion_comercial(sesion, mensaje_usuario: str, respuesta_bot: str):
    if sesion is None:
        return
    historial = list(sesion.historial_mensajes or [])
    historial.append({'role': 'user', 'content': (mensaje_usuario or '')[:3000]})
    historial.append({'role': 'assistant', 'content': (respuesta_bot or '')[:3000]})
    if len(historial) > 20:
        historial = historial[-20:]
    sesion.historial_mensajes = historial
    sesion.save(update_fields=['historial_mensajes', 'fecha_ultimo_mensaje'])


def _bot_comercial_diagnosticar_imagen(media_url: str, media_type: str, cliente=None) -> str:
    """Diagnóstico preliminar de imagen de cultivo (hipótesis, sin veredicto cerrado)."""
    from core.bot_comercial.vision import diagnosticar_imagen_cultivo

    return diagnosticar_imagen_cultivo(media_url, media_type, cliente=cliente)


def _procesar_bot_comercial_twilio_webhook(post_data, forzar_canal=False):
    """Webhook Twilio dedicado para bot comercial (texto libre, voz e imagen)."""
    from core.rag_comercial_manager import rag_comercial_manager

    status = post_data.get('MessageStatus', post_data.get('SmsStatus', ''))
    if status and status.lower() in ['queued', 'sending', 'sent', 'delivered', 'undelivered', 'failed', 'read']:
        _registrar_estado_twilio_callback(post_data)
        return

    msg_body = (post_data.get('Body', '') or '').strip()
    msg_from = post_data.get('From', '')
    msg_to = post_data.get('To', '')
    from_number_respuesta = msg_to
    msg_sid = post_data.get('MessageSid', f'botcom_{timezone.now().timestamp()}')
    num_media = int(post_data.get('NumMedia', 0) or 0)
    media_type = post_data.get('MediaContentType0', '') or ''
    media_url = post_data.get('MediaUrl0', '') or ''

    # Evita doble respuesta si Twilio reintenta el mismo webhook.
    if msg_sid and WhatsappLog.objects.filter(
        mensaje_id=msg_sid,
        tipo='INCOMING',
        agente_usado='BOT_COMERCIAL',
    ).exists():
        logger.info("♻️ Bot comercial: webhook duplicado ignorado | sid=%s", msg_sid)
        return

    from core.eventos_ia import set_trace_id
    set_trace_id()

    if msg_from.startswith('whatsapp:'):
        msg_from = msg_from.replace('whatsapp:', '')
    if msg_to.startswith('whatsapp:'):
        msg_to = msg_to.replace('whatsapp:', '')
    import re
    telefono_limpio = re.sub(r'\D', '', msg_from)
    to_limpio = re.sub(r'\D', '', msg_to)
    if len(telefono_limpio) == 10:
        telefono_limpio = f"57{telefono_limpio}"

    from core.bot_comercial_routing import es_numero_comercial_conocido
    if (not forzar_canal) and to_limpio and not es_numero_comercial_conocido(to_limpio):
        logger.info(
            "Webhook bot comercial ignorado: To=%s no es línea Nat (global/org/sandbox)",
            to_limpio,
        )
        return

    if num_media > 0 and ('audio' in media_type or 'ogg' in media_type):
        transcripcion = _transcribir_audio_twilio(media_url, media_type=media_type)
        if transcripcion:
            msg_body = transcripcion
        elif not msg_body:
            msg_body = '[AUDIO_NO_TRANSCRITO]'

    if not msg_body and num_media == 0:
        logger.info("ℹ️ Bot comercial: webhook sin contenido ignorado | sid=%s", msg_sid)
        return

    WhatsappLog.objects.create(
        telefono=telefono_limpio,
        mensaje=msg_body or f'[MEDIA:{media_type}]',
        mensaje_id=msg_sid,
        tipo='INCOMING',
        es_audio=('audio' in media_type),
        agente_usado='BOT_COMERCIAL',
    )

    try:
        from core.eventos_ia import emit_webhook_recibido
        from core.ai_capabilities import resolver_ai_capability

        if resolver_ai_capability('eventos_ia'):
            emit_webhook_recibido(
                mensaje=msg_body or f'[MEDIA:{media_type}]',
                telefono=telefono_limpio,
                canal='whatsapp_comercial',
            )
    except Exception:
        pass

    msg_normalizado = re.sub(r'\s+', ' ', (msg_body or '').strip().lower())
    memoria_turnos = int(getattr(settings, 'BOT_COMERCIAL_MEMORY_TURNOS', 12) or 12)
    memoria_chars = int(getattr(settings, 'BOT_COMERCIAL_MEMORY_MAX_CHARS', 3600) or 3600)
    historial_chat = _bot_comercial_historial_reciente(
        telefono=telefono_limpio,
        max_turnos=memoria_turnos,
        max_chars=memoria_chars,
    )
    if historial_chat:
        logger.info(
            "🧠 Memoria chat comercial aplicada | telefono=%s | chars=%s",
            telefono_limpio,
            len(historial_chat),
        )

    es_saludo = bool(
        re.match(
            r'^(hola|buenas|buenos dias|buen día|buenas tardes|buenas noches|hey|que tal|qué tal)\b',
            msg_normalizado,
        )
    )

    cliente_id_cfg = int(
        getattr(settings, 'BOT_COMERCIAL_CLIENTE_ID', 0) or 0
    )
    canal_rag = str(getattr(settings, 'BOT_COMERCIAL_RAG_CANAL', 'bot_comercial') or 'bot_comercial')

    from core.nati import armar_saludo_inicial, armar_saludo_menu, armar_cliente_ids_rag, resolver_cliente_desde_numero_whatsapp

    cliente_nati = resolver_cliente_desde_numero_whatsapp(msg_to)
    if not cliente_nati and cliente_id_cfg:
        try:
            cliente_nati = Cliente.objects.filter(id=cliente_id_cfg, activo=True).first()
        except Exception as e:
            logger.warning(
                "Bot comercial: no se pudo cargar Cliente id=%s para Nat: %s",
                cliente_id_cfg, e,
            )

    sesion_comercial = _obtener_o_crear_sesion_comercial(
        telefono=telefono_limpio,
        cliente=cliente_nati,
        horas_expira=int(getattr(settings, 'BOT_COMERCIAL_SESSION_HOURS', 4) or 4),
    )

    consulta = msg_body or 'Necesito asesoría agrícola'
    rag_chunks = []

    ctx_agro = None
    bloque_contexto_agro = ''
    try:
        from core.ai_capabilities import resolver_ai_capability
        from core.contexto_agro import actualizar_contexto_desde_mensaje, formatear_bloque_contexto_para_prompt

        if resolver_ai_capability('nati_structured_context', cliente=cliente_nati):
            ctx_agro = actualizar_contexto_desde_mensaje(sesion_comercial, msg_body)
            bloque_contexto_agro = formatear_bloque_contexto_para_prompt(ctx_agro)
    except Exception:
        pass

    routing = None
    # Nat NO usa keywords de cursos (listo/continuar). Solo escapes propios.
    if es_saludo:
        texto_respuesta = armar_saludo_inicial(cliente_nati)
    elif msg_normalizado in ['asesoria', 'asesoría', 'reiniciar', 'ayuda nat']:
        try:
            from core.nat_diagnostico import reiniciar_diagnostico

            reiniciar_diagnostico(ctx_agro)
        except Exception:
            pass
        texto_respuesta = armar_saludo_menu(cliente_nati)
    else:
        diagnostico_vision = ''
        if num_media > 0 and media_type.startswith('image') and media_url:
            diagnostico_vision = _bot_comercial_diagnosticar_imagen(
                media_url, media_type, cliente=cliente_nati,
            )

        from core.bot_comercial.vision import es_analisis_vision_util

        vision_util = es_analisis_vision_util(diagnostico_vision)

        consulta = msg_body or 'Necesito asesoría agrícola'
        # Solo inyectar análisis real (no mensajes de error/capability) al LLM
        if vision_util:
            consulta = f"{consulta}\n\nDiagnóstico preliminar imagen: {diagnostico_vision}"

        texto_respuesta = None
        try:
            from core.nat_diagnostico import siguiente_pregunta_diagnostico

            pregunta_diag = siguiente_pregunta_diagnostico(
                ctx_agro,
                msg_body,
                tiene_imagen=bool(diagnostico_vision),
            )
            if pregunta_diag and vision_util:
                # Foto útil + dato pendiente: análisis + pregunta, sin rótulo extra
                texto_respuesta = (
                    f"{diagnostico_vision.strip()}\n\n{pregunta_diag.strip()}"
                )
            elif pregunta_diag:
                texto_respuesta = pregunta_diag
            elif vision_util and not (msg_body or '').strip():
                pass
        except Exception:
            pass

        rag_chunks: list = []
        routing = None
        if texto_respuesta is None:
            cliente_ids_consulta = armar_cliente_ids_rag(cliente_nati)

            contexto_rag = ''
            contexto_web = ''

            from core.catalogo_precios import (
                buscar_precios,
                es_consulta_catalogo,
                formatear_contexto_precios,
            )
            contexto_precios_db = ''
            if es_consulta_catalogo(consulta) and cliente_ids_consulta:
                productos_precio = buscar_precios(
                    [i for i in cliente_ids_consulta if i != 0] or cliente_ids_consulta,
                    consulta,
                )
                if productos_precio:
                    contexto_precios_db = formatear_contexto_precios(productos_precio)
                    logger.info(
                        "💰 Precios Postgres | hits=%s | clientes=%s",
                        len(productos_precio),
                        cliente_ids_consulta,
                    )

            if rag_comercial_manager.disponible:
                canales_consulta = []
                for c in [canal_rag, 'bot_comercial']:
                    if c and c not in canales_consulta:
                        canales_consulta.append(c)

                rag_max = int(getattr(settings, 'BOT_COMERCIAL_RAG_MAX_CHARS', 2500) or 2500)
                rag_max = max(400, min(rag_max, 4000))
                try:
                    top_k = int(getattr(settings, 'BOT_COMERCIAL_RAG_TOP_K', 9) or 9)
                except (TypeError, ValueError):
                    top_k = 9
                top_k = max(3, min(top_k, 20))

                for canal in canales_consulta:
                    rag_result = rag_comercial_manager.obtener_contexto_varios_clientes(
                        cliente_ids_consulta,
                        canal,
                        consulta,
                        max_chars=rag_max,
                        top_k_por_scope=top_k,
                        retornar_chunks=True,
                    )
                    contexto_rag, rag_chunks = rag_result
                    if contexto_rag:
                        logger.info(
                            "🧠 RAG comercial unificado | canal=%s | contexto_chars=%s | clientes=%s",
                            canal,
                            len(contexto_rag),
                            cliente_ids_consulta,
                        )
                        try:
                            from core.eventos_ia import emit_rag_query_executed

                            emit_rag_query_executed(
                                pregunta=consulta,
                                cliente=cliente_nati,
                                canal='whatsapp_comercial',
                                chunks_count=len(rag_chunks),
                                contexto_chars=len(contexto_rag),
                                chunks=rag_chunks,
                                metadata={'origen': 'rag_comercial', 'canal_rag': canal},
                            )
                        except Exception:
                            pass
                        break

            if not contexto_rag and getattr(settings, 'BOT_COMERCIAL_RAG_FILE_FALLBACK', True):
                rag_fb = int(getattr(settings, 'BOT_COMERCIAL_RAG_MAX_CHARS', 1600) or 1600)
                rag_fb = max(400, min(rag_fb + 200, 4000))
                fb_docs = int(getattr(settings, 'BOT_COMERCIAL_RAG_FALLBACK_MAX_DOCS', 2) or 2)
                fb_rows = int(getattr(settings, 'BOT_COMERCIAL_RAG_FALLBACK_XLSX_ROWS', 800) or 800)
                contexto_rag = _contexto_fallback_desde_documentos(
                    cliente_ids=cliente_ids_consulta,
                    pregunta=consulta,
                    max_chars=rag_fb,
                    max_docs=fb_docs,
                    xlsx_max_rows=fb_rows,
                )
                if contexto_rag:
                    logger.info("🧠 RAG fallback documental usado | contexto_chars=%s", len(contexto_rag))

            try:
                from core.agrosavia_connector import buscar_agrosavia, formatear_contexto_agrosavia

                if len(contexto_rag or '') < 800:
                    ctx_agrosavia = formatear_contexto_agrosavia(buscar_agrosavia(consulta, size=3))
                    if ctx_agrosavia:
                        contexto_rag = (
                            f"{contexto_rag}\n\n{ctx_agrosavia}".strip()
                            if contexto_rag
                            else ctx_agrosavia
                        )
                        logger.info("🌾 AGROSAVIA live | chars=%s", len(ctx_agrosavia))
            except Exception:
                pass

            if contexto_precios_db:
                contexto_rag = (
                    f"{contexto_precios_db}\n\n{contexto_rag}".strip()
                    if contexto_rag
                    else contexto_precios_db
                )

            from core.nat_router import decidir_routing_nat

            routing = decidir_routing_nat(
                consulta,
                rag_chunks=rag_chunks,
                tiene_rag_texto=bool(contexto_rag),
                contexto_rag_chars=len(contexto_rag or ''),
                ctx_agro=ctx_agro,
                diagnostico_vision=diagnostico_vision,
            )
            logger.info(
                "🧭 Nat routing | modelo=%s modo=%s razon=%s web=%s sim=%s",
                routing.modelo,
                routing.modo,
                routing.razon,
                routing.usar_web,
                routing.rag_max_similitud,
            )

            if routing.usar_web and not contexto_web:
                from core.nati import buscar_en_web_colombia

                contexto_web = buscar_en_web_colombia(consulta) or _contexto_fallback_web_agro(
                    pregunta=consulta,
                    max_chars=1800,
                )
                if contexto_web:
                    logger.info("🌐 Web complementaria (RAG débil/ausente) | chars=%s", len(contexto_web))

            texto_respuesta = _bot_comercial_respuesta_catalogo(
                pregunta=consulta,
                contexto_rag=contexto_rag,
                diagnostico_vision=diagnostico_vision,
                contexto_web=contexto_web,
                historial_chat=historial_chat,
                cliente=cliente_nati,
                sesion_comercial=sesion_comercial,
                bloque_contexto_agro=bloque_contexto_agro,
                routing=routing,
                rag_chunks=rag_chunks,
                ctx_agro=ctx_agro,
            )

    if (
        not es_saludo
        and msg_normalizado not in ['asesoria', 'asesoría', 'reiniciar', 'ayuda nat']
        and routing is not None
        and routing.modo in ('tecnico', 'catalogo', 'ambiguo')
    ):
        try:
            import uuid

            from core.eventos_ia import get_or_create_trace_id
            from core.knowledge_studio import crear_candidata_hitl

            tid = get_or_create_trace_id()
            trace_uuid = uuid.UUID(tid) if tid else None
            crear_candidata_hitl(
                cliente=cliente_nati,
                sesion=sesion_comercial,
                telefono=telefono_limpio,
                pregunta=consulta,
                respuesta_nati=texto_respuesta,
                contexto_agro=ctx_agro.to_dict() if ctx_agro else {},
                chunks_rag=rag_chunks,
                trace_id=trace_uuid,
            )
        except Exception:
            pass

    try:
        resultado_envio = enviar_whatsapp_twilio(
            telefono_limpio,
            texto_respuesta,
            from_number=from_number_respuesta,
        )
        if not resultado_envio.get('success'):
            raise RuntimeError(str(resultado_envio.get('response') or 'Error enviando por Twilio'))

        try:
            from core.eventos_ia import emit_mensaje_enviado

            emit_mensaje_enviado(
                telefono=telefono_limpio,
                texto=texto_respuesta,
                mensaje_id=resultado_envio.get('mensaje_id'),
                cliente=cliente_nati,
                canal='whatsapp_comercial',
                agente='nati',
            )
        except Exception:
            pass

        WhatsappLog.objects.create(
            telefono=telefono_limpio,
            mensaje=texto_respuesta[:1500],
            mensaje_id=resultado_envio.get('mensaje_id'),
            tipo='SENT',
            agente_usado='BOT_COMERCIAL',
        )
        # Fotos de productos recomendados (catálogo) — mensaje aparte por WhatsApp
        try:
            from core.bot_comercial.productos_media import (
                enviar_fotos_productos_whatsapp,
                fotos_productos_para_whatsapp,
            )

            fotos = fotos_productos_para_whatsapp(cliente_nati, texto_respuesta, limite=2)
            if fotos:
                envios = enviar_fotos_productos_whatsapp(
                    telefono_limpio,
                    fotos,
                    from_number=from_number_respuesta,
                )
                for item in envios:
                    ok = bool(item.get('success'))
                    WhatsappLog.objects.create(
                        telefono=telefono_limpio,
                        mensaje=(
                            f"[FOTO PRODUCTO] {item.get('nombre', '')}"
                            if ok
                            else f"[FOTO PRODUCTO FALLÓ] {item.get('nombre', '')}: {item.get('response', '')}"
                        )[:500],
                        mensaje_id=item.get('mensaje_id'),
                        tipo='SENT',
                        estado='SENT' if ok else 'FAILED',
                        agente_usado='BOT_COMERCIAL',
                    )
                    if not ok:
                        logger.warning(
                            'Nat foto producto no enviada | prod=%s | err=%s',
                            item.get('nombre'),
                            item.get('response'),
                        )
        except Exception:
            logger.exception('Nat: no se pudieron enviar fotos de producto')

        _actualizar_sesion_comercial(
            sesion=sesion_comercial,
            mensaje_usuario=msg_body or consulta,
            respuesta_bot=texto_respuesta,
        )
    except Exception as e:
        logger.error(f"❌ Error respondiendo bot comercial: {e}")

