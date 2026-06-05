from __future__ import annotations

import os
import re
from typing import Any

from django.conf import settings
from django.utils import timezone

from .gei_flujos import es_formulario_balance_gei
from .models import (
    CAMPOS_GEI_7,
    CAMPOS_GEI_EXTENSION,
    FichaGEI,
    FlujoPregunta,
    SesionFormulario,
    TipoFormulario,
)
from .whatsapp_gei import enviar_balance_gei_whatsapp


def _formatear_pregunta(n: int, total: int, pregunta: FlujoPregunta) -> str:
    cuerpo = (pregunta.pregunta_texto or "").strip()
    return f"Pregunta {n} de {total} 🌱\n\n{cuerpo}"


def _pasos_ordenados(form: TipoFormulario) -> list[FlujoPregunta]:
    return list(FlujoPregunta.objects.filter(formulario=form).order_by("orden", "id"))


def _campo_ficha_valido(nombre: str) -> bool:
    try:
        FichaGEI._meta.get_field(nombre)
        return True
    except Exception:
        return False


def guardar_en_destino(sesion: SesionFormulario, campo: str, valor: Any) -> None:
    ficha = sesion.ficha
    if not _campo_ficha_valido(campo):
        raise ValueError(f"Campo desconocido en FichaGEI: {campo}")
    setattr(ficha, campo, valor)
    ficha.save()


def _parseo_float_directo(texto: str) -> float | None:
    t = (texto or "").strip().replace(",", ".")
    m = re.search(r"[-+]?[0-9]*\.?[0-9]+", t)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


# ============================================================================
# Conversiones para el extractor LLM de cantidades agrícolas colombianas.
# Se inyectan como tabla de referencia en el system prompt para que el modelo
# aprenda a traducir frases como "5 fanegadas", "tres bultos de 50",
# "media cuadra", "8 arrobas", etc., a la unidad pedida en cada paso.
# Fuentes: equivalencias usadas en extensión rural colombiana (DANE, ICA, FNC).
# ============================================================================
TABLA_CONVERSIONES_AGROCOL_PROMPT = """\
TABLA DE EQUIVALENCIAS COLOMBIANAS (úsala SIEMPRE para convertir):

ÁREA (a hectáreas, ha):
- 1 fanegada = 0.64 ha (Cundinamarca/Boyacá; en otras regiones puede ser ~0.6 ha)
- 1 cuadra (Antioquia/Llanos) = 0.625 ha
- 1 plaza (Tolima, Huila) = 0.64 ha
- 1 manzana (Centroamérica/Costa) = 0.7 ha
- 1 hectárea (ha) = 10 000 m²
- 1 acre = 0.4047 ha
- 1 m² = 0.0001 ha

PESO (a kilogramos, kg):
- 1 bulto = 50 kg (default agrícola: urea, dap, kcl, abonos, café pergamino seco)
- 1 saco = 50 kg (igual a bulto si no se especifica)
- 1 costal = 50 kg
- 1 carga café = 125 kg (2 bultos, café pergamino seco)
- 1 arroba (@) = 12.5 kg
- 1 quintal = 50 kg (Colombia, equivale al bulto/saco; en otros países 46 kg)
- 1 tonelada (t, tn) = 1000 kg
- 1 libra (lb) = 0.45 kg
- 1 gramo (g) = 0.001 kg

VOLUMEN/LÍQUIDO (a litros, L):
- 1 galón (US) = 3.785 L
- 1 caneca = 200 L (default; si dicen caneca chiquita, 20 L)
- 1 botella = 0.75 L (default)

CANTIDAD (a unidades sueltas):
- 1 docena = 12
- 1 ciento = 100
- 1 millar = 1000

ENERGÍA (a kWh):
- 1 kWh = 1 kWh
- 1 MWh = 1000 kWh

INTERPRETACIÓN DE FRASES IMPRECISAS:
- "más o menos 5", "como 5", "unos 5", "casi 5", "cerca de 5" → 5
- "media" o "1/2" → 0.5
- "un cuarto", "1/4" → 0.25
- "tres cuartos", "3/4" → 0.75
- "y medio", "y media" → +0.5 al número anterior (ej: "dos y medio" = 2.5)
- "un par" → 2
- "varios", "muchos", "poquito" → null (no es cuantificable)

OPERACIONES MATEMÁTICAS:
- Si el usuario dice "5 bultos por planta a 1000 plantas" → calcula 5 × 1000 = 5000
  bultos. Convierte a la unidad pedida si aplica (5000 bultos = 250 000 kg).
- Si dice "3 veces al año por 200 g por planta a 1000 plantas" → 3 × 200 × 1000 = 600 000 g = 600 kg.
- Si menciona porcentajes (ej. "urea 46%"), considéralo si la unidad pedida es "kg de N";
  si no es relevante, ignóralo.
"""


def _llm_extrae_numero(texto: str, unidad: str, pregunta_texto: str = "") -> float | None:
    api_key = (getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY", "") or "").strip()
    if not api_key:
        return _parseo_float_directo(texto)
    try:
        from openai import OpenAI
    except ImportError:
        return _parseo_float_directo(texto)

    client = OpenAI(api_key=api_key)
    model = getattr(settings, "FORMULARIO_GEI_LLM_MODELO", "gpt-4o-mini")
    u = (unidad or "la unidad indicada en la pregunta").strip() or "unidad acordada"
    contexto_pregunta = (pregunta_texto or "").strip()[:600]
    sysm = (
        "Eres un extractor de datos numéricos para un formulario de huella de carbono "
        "(GEI) dirigido a productores agropecuarios colombianos. Tu único trabajo es "
        f"devolver el número equivalente en la unidad: {u}. "
        "Aplicas la TABLA DE EQUIVALENCIAS para convertir cuando el usuario use otra unidad. "
        "Si el usuario describe una operación (ej. '5 bultos × 200 plantas'), "
        "haces la cuenta y devuelves el resultado en la unidad pedida.\n\n"
        + TABLA_CONVERSIONES_AGROCOL_PROMPT
        + "\n\nFORMATO DE SALIDA (estricto):\n"
        "- Devuelve ÚNICAMENTE el número (puede tener decimales con punto: 2.5).\n"
        "- NO escribas la unidad, NO expliques, NO uses comas como separador decimal.\n"
        "- Si no se puede extraer un número claro o el usuario dice 'no sé' / 'no aplica', "
        "  devuelve exactamente: null"
    )
    contenido_user = (
        f"Pregunta del formulario: {contexto_pregunta}\n\n"
        f"Respuesta del productor: {(texto or '')[:1800]}"
    )
    try:
        r = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": sysm},
                {"role": "user", "content": contenido_user},
            ],
        )
    except Exception:
        return _parseo_float_directo(texto)
    raw = (r.choices[0].message.content or "").strip()
    if raw.lower() in ("null", "none", "nan", "n/a", ""):
        return None
    return _parseo_float_directo(raw)


def parsear_respuesta(texto: str, pregunta: FlujoPregunta) -> Any | None:
    t = (texto or "").strip()
    if pregunta.tipo_dato == "float":
        if pregunta.usar_llm_parseo:
            u = (pregunta.unidad_parseo or "").strip() or "1"
            return _llm_extrae_numero(t, u, pregunta_texto=(pregunta.pregunta_texto or ""))
        return _parseo_float_directo(t)
    if pregunta.tipo_dato == "text":
        return t[:500] if t else None
    if pregunta.tipo_dato == "bool":
        s = t.lower()
        if s in ("sí", "si", "s", "1", "verdadero", "true", "claro", "de acuerdo", "sí."):
            return True
        if s in ("no", "n", "0", "falso", "false"):
            return False
        return None
    if pregunta.tipo_dato == "choice":
        for o in (pregunta.opciones_choice or "").split("|"):
            o = o.strip()
            if o and t.lower() == o.lower():
                return o
        return None
    return None


def _validar_rango(
    pregunta: FlujoPregunta, valor: float
) -> tuple[bool, str | None]:
    if pregunta.tipo_dato != "float":
        return True, None
    x = float(valor)
    if pregunta.rango_min is not None and x < float(pregunta.rango_min):
        return False, f"el mínimo permitido es {pregunta.rango_min}"
    if pregunta.rango_max is not None and x > float(pregunta.rango_max):
        return False, f"el máximo permitido es {pregunta.rango_max}"
    return True, None


def _resumen_ficha(ficha: FichaGEI) -> str:
    lineas: list[str] = []
    for c in list(CAMPOS_GEI_7) + list(CAMPOS_GEI_EXTENSION):
        v = getattr(ficha, c, None)
        if v is not None and v != "":
            lineas.append(f"• {c.replace('_', ' ')}: {v}")
    if ficha.tiene_bosque is False and not any("bosque" in ln for ln in lineas):
        lineas.append("• tiene bosque: no")
    if not lineas:
        return "Aún quedan datos vacíos. Si lo desea, su facilitador le puede acompañar a completarlos."
    return "\n".join(lineas)


def _ajuste_valor_ficha(pregunta: FlujoPregunta, valor: Any) -> Any:
    c = (pregunta.campo_destino or "").strip()
    f = FichaGEI._meta.get_field(c)
    if f.get_internal_type() in ("CharField", "TextField",):
        return str(valor)[:f.max_length] if f.max_length else str(valor)
    if c == "num_plantas" and isinstance(valor, (int, float)):
        return max(0, int(round(float(valor))))
    if f.get_internal_type() == "FloatField" and isinstance(valor, (int, float)):
        return float(valor)
    if f.get_internal_type() == "BooleanField":
        return bool(valor)
    if f.get_internal_type() in ("IntegerField", "PositiveIntegerField", "PositiveSmallIntegerField"):
        try:
            return int(float(valor))
        except (TypeError, ValueError):
            return None
    return valor


def iniciar_sesion_formulario(
    estudiante,
    tipo_formulario: TipoFormulario,
    progreso=None,
    modulo_siguiente=None,
) -> str:
    pasos = _pasos_ordenados(tipo_formulario)
    if not pasos:
        return (
            "En este momento el formulario no está disponible. Puede comentar con su facilitador, por favor. "
        )
    es_balance = es_formulario_balance_gei(tipo_formulario)
    ficha = (
        FichaGEI.objects.filter(
            estudiante=estudiante,
            curso=tipo_formulario.curso,
        )
        .order_by("-fecha_update", "-id")
        .first()
    )
    if not ficha:
        ficha = FichaGEI.objects.create(
            estudiante=estudiante,
            cliente=estudiante.cliente,
            curso=tipo_formulario.curso,
        )

    SesionFormulario.objects.create(
        estudiante=estudiante,
        formulario=tipo_formulario,
        paso_actual=0,
        ficha=ficha,
        progreso=progreso,
        modulo_siguiente=modulo_siguiente,
    )

    if es_balance:
        intro = (
            f"Para cerrar su *balance GEI* necesitamos *{len(pasos)} datos más* "
            f"(combustible, residuos y bosque). Luego le enviamos el resultado por aquí.\n\n"
            f"Puede escribir *OMITIR* en lo que no sepa.\n\n"
        )
    else:
        intro = (
            f"*Primera parte* de los datos de su finca: *{len(pasos)} preguntas* "
            f"para avanzar al siguiente módulo.\n\n"
            f"Puede escribir *OMITIR* donde lo permita el paso.\n\n"
        )
    p0 = pasos[0]
    return intro + _formatear_pregunta(1, len(pasos), p0)


def _cerrar_sesion(sesion: SesionFormulario, pasos: list[FlujoPregunta]) -> str:
    sesion.completado = True
    sesion.fecha_update = timezone.now()
    sesion.save()
    ficha = sesion.ficha
    if sesion.progreso_id and sesion.modulo_siguiente_id:
        p = sesion.progreso
        p.modulo_actual = sesion.modulo_siguiente
        from core.module_steps import reset_progreso_pasos_modulo
        reset_progreso_pasos_modulo(p, save=False)
        p.fecha_ultimo_avance = timezone.now()
        p.save()
    r = _resumen_ficha(ficha)
    es_balance = es_formulario_balance_gei(sesion.formulario)
    cierre_balance = ""
    if es_balance:
        enviado = enviar_balance_gei_whatsapp(ficha, sesion.estudiante)
        if enviado:
            cierre_balance = (
                "\n\n📊 *Le acabamos de enviar por aquí el resultado de su balance GEI.* "
                "Revíselo con calma."
            )
        else:
            cierre_balance = (
                "\n\n📊 Su balance quedó calculado en el sistema. "
                "Si no recibe el resumen, comente con su facilitador."
            )

    etapa = "el balance GEI" if es_balance else "la primera parte de los datos"
    return (
        f"Gracias, ya concluimos *{etapa}*. "
        "Resumen guardado en su ficha:\n\n"
        f"{r}"
        f"{cierre_balance}\n\n"
        "Escriba *listo* para seguir con el módulo siguiente, o *menú* si necesita otra opción."
    )


def _omision_forzada_y_avance(
    sesion: SesionFormulario,
    pasos: list[FlujoPregunta],
    _pregunta: FlujoPregunta,
    idx: int,
) -> str:
    """Tras reintentos agotados: avanza sin guardar."""
    sesion.paso_actual = idx + 1
    sesion.reintentos_paso = 0
    sesion.save()
    if sesion.paso_actual >= len(pasos):
        return _cerrar_sesion(sesion, pasos)
    sig = pasos[sesion.paso_actual]
    return _formatear_pregunta(sesion.paso_actual + 1, len(pasos), sig)


def manejar_mensaje_formulario(estudiante, texto_mensaje: str) -> str:
    sesion = (
        SesionFormulario.objects.select_related("formulario", "ficha", "progreso", "modulo_siguiente")
        .filter(estudiante=estudiante, completado=False)
        .order_by("-fecha_inicio", "-id")
        .first()
    )
    if not sesion:
        return "No hay un formulario activo. Escriba *menú* para continuar, por favor. "

    form = sesion.formulario
    pasos = _pasos_ordenados(form)
    if not pasos:
        return "Faltan los pasos del formulario en el sistema. Puede comentar con su facilitador, por favor."

    idx = int(sesion.paso_actual or 0)
    if idx < 0 or idx >= len(pasos):
        sesion.completado = True
        sesion.save()
        return "El formulario ya no tiene paso pendiente. Escriba *listo* o *menú*, por favor."

    pregunta = pasos[idx]
    max_re = sesion.max_reintentos
    tnorm = (texto_mensaje or "").strip()
    tlower = tnorm.lower()
    omi = tlower in ("omitir", "omito", "no aplica", "n/a")

    if omi and pregunta.es_opcional:
        sesion.paso_actual = idx + 1
        sesion.reintentos_paso = 0
        sesion.save()
        if sesion.paso_actual >= len(pasos):
            return _cerrar_sesion(sesion, pasos)
        sig = pasos[sesion.paso_actual]
        return _formatear_pregunta(sesion.paso_actual + 1, len(pasos), sig)

    if omi and not pregunta.es_opcional:
        return "Este paso no se puede omitir. Indique un valor, por favor."

    valor = parsear_respuesta(tnorm, pregunta)
    v_ok = True
    razon = ""

    if pregunta.tipo_dato == "float":
        if valor is None:
            v_ok, razon = False, "no pudo leerse un número claro. "
        else:
            ok, err = _validar_rango(pregunta, float(valor))
            if not ok:
                v_ok, razon = False, (err or "")
    elif pregunta.tipo_dato == "text":
        v_ok = bool((valor or "").strip())
    elif pregunta.tipo_dato == "bool":
        v_ok = isinstance(valor, bool)
    elif pregunta.tipo_dato == "choice":
        v_ok = valor is not None

    if v_ok:
        try:
            if pregunta.tipo_dato == "text":
                guardar_en_destino(sesion, pregunta.campo_destino, str(valor).strip()[:500])
            else:
                guardar_en_destino(sesion, pregunta.campo_destino, _ajuste_valor_ficha(pregunta, valor))
        except Exception:
            v_ok, razon = False, "no pudo almacenarse. "

    if v_ok:
        sesion.paso_actual = idx + 1
        sesion.reintentos_paso = 0
        sesion.save()
        if sesion.paso_actual >= len(pasos):
            return _cerrar_sesion(sesion, pasos)
        sig = pasos[sesion.paso_actual]
        return _formatear_pregunta(sesion.paso_actual + 1, len(pasos), sig)

    if sesion.reintentos_paso < max_re:
        sesion.reintentos_paso = int(sesion.reintentos_paso) + 1
        sesion.save(update_fields=["reintentos_paso", "fecha_update"])
        dft = (pregunta.texto_reintento or "").strip() or (
            f"No pudo validarse. {razon}Intente otra expresión breve, en una sola frase, por favor."
        )
        return dft
    return _omision_forzada_y_avance(sesion, pasos, pregunta, idx)
