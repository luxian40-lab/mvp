from __future__ import annotations

import os
import re
from typing import Any

from django.conf import settings
from django.utils import timezone

from .models import CAMPOS_GEI_7, FichaGEI, FlujoPregunta, SesionFormulario, TipoFormulario


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


def _llm_extrae_numero(texto: str, unidad: str) -> float | None:
    api_key = (getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY", "") or "").strip()
    if not api_key:
        return _parseo_float_directo(texto)
    try:
        from openai import OpenAI
    except ImportError:
        return _parseo_float_directo(texto)

    client = OpenAI(api_key=api_key)
    model = getattr(settings, "FORMULARIO_GEI_LLM_MODELO", "gpt-4o-mini")
    u = (unidad or "la indicada en la pregunta").strip() or "unidad acordada"
    sysm = (
        "Eres un extractor de datos numéricos. El usuario "
        f"describe una cantidad agrícola en español colombiano. Devuelve ÚNICAMENTE el número en la unidad {u}. "
        "Si no puede extraer un número, devuelve null."
    )
    r = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": sysm},
            {"role": "user", "content": (texto or "")[:2000]},
        ],
    )
    raw = (r.choices[0].message.content or "").strip()
    if raw.lower() in ("null", "none", "nan", "n/a", ""):
        return None
    return _parseo_float_directo(raw)


def parsear_respuesta(texto: str, pregunta: FlujoPregunta) -> Any | None:
    t = (texto or "").strip()
    if pregunta.tipo_dato == "float":
        if pregunta.usar_llm_parseo:
            u = (pregunta.unidad_parseo or "").strip() or "1"
            return _llm_extrae_numero(t, u)
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
    for c in CAMPOS_GEI_7:
        v = getattr(ficha, c, None)
        if v is not None and v != "":
            lineas.append(f"• {c.replace('_', ' ')}: {v}")
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

    intro = (
        f"Necesitamos completar *{len(pasos)} datos sencillos* sobre su finca para avanzar. "
        f"Esto hace parte de: *{tipo_formulario.nombre}*.\n\n"
        f"En los pasos que lo permitan, puede escribir *OMITIR* para dejarlo en blanco. Gracias por su paciencia.\n\n"
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
        p.fecha_ultimo_avance = timezone.now()
        p.save()
    r = _resumen_ficha(ficha)
    return (
        "Gracias, ya concluimos *la recolección de datos* de esta etapa. "
        "A continuación el resumen enviado a su ficha (si hay alguna duda, puede anotarla a su facilitador):\n\n"
        f"{r}\n\n"
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
