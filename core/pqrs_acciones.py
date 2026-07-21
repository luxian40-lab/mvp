"""Acciones seguras que el agente PQRS puede ejecutar con contexto del estudiante."""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

ACCIONES_VALIDAS = frozenset({
    'ninguna',
    'corregir_datos',
    'explicar_progreso',
    'reenviar_modulo',
    'escalar',
})

CAMPOS_CORRECCION = frozenset({'nombre', 'municipio', 'cedula'})

CIERRE_RETORNO_CURSO = (
    "Para seguir con el curso escriba *listo*."
)


def _progreso_activo(estudiante):
    from core.models import ProgresoEstudiante

    ctx = estudiante.contexto_temporal or {}
    curso_id = ctx.get('curso_activo_id')
    qs = (
        ProgresoEstudiante.objects.filter(
            estudiante=estudiante,
            completado=False,
            curso__activo=True,
        )
        .select_related('curso', 'modulo_actual')
        .order_by('-fecha_inicio')
    )
    if curso_id:
        enfocado = qs.filter(curso_id=int(curso_id)).first()
        if enfocado:
            return enfocado
    return qs.first()


def texto_explicar_progreso(estudiante) -> str:
    """Información real de avance (sin inventar)."""
    from core.drip_schedule import drip_bloquea_siguiente_modulo
    from core.models import ProgresoEstudiante

    progresos = list(
        ProgresoEstudiante.objects.filter(
            estudiante=estudiante,
            completado=False,
            curso__activo=True,
        )
        .select_related('curso', 'modulo_actual')
        .order_by('-fecha_inicio')
    )
    nombre = (estudiante.nombre or '').strip().split()
    saludo = f"Hola {nombre[0]}, " if nombre else ''

    if not progresos:
        return (
            f"{saludo}aún no veo un curso activo en su perfil.\n\n"
            "Si cree que es un error, descríbalo y lo revisamos. "
            f"{CIERRE_RETORNO_CURSO}"
        )

    lineas = [f"{saludo}este es su avance actual:\n"]
    for p in progresos:
        curso = p.curso
        emoji = (curso.emoji or '📚').strip() if curso else '📚'
        avance = p.porcentaje_avance()
        lineas.append(f"*{emoji} {curso.nombre}* — {avance}%")
        if p.modulo_actual:
            m = p.modulo_actual
            lineas.append(f"  Módulo {m.numero}: {m.titulo}")
            if drip_bloquea_siguiente_modulo(p, m):
                lineas.append(
                    "  ⏳ Hay una espera programada (drip) antes del siguiente módulo."
                )
        lineas.append('')

    lineas.append(CIERRE_RETORNO_CURSO)
    return '\n'.join(lineas).strip()


def texto_reenviar_modulo(estudiante) -> str:
    """Reenvía el material del módulo/paso actual sin avanzar el progreso."""
    from core.module_steps import (
        entregar_bloque_secciones_desde_paso,
        mensaje_recordatorio_paso_actual,
        modulo_usa_pasos,
        pasos_activos_qs,
    )
    from core.response_templates import obtener_video_url

    progreso = _progreso_activo(estudiante)
    if not progreso or not progreso.curso:
        return (
            "No encontré un módulo activo para reenviar.\n\n"
            f"{CIERRE_RETORNO_CURSO}"
        )

    modulo = progreso.modulo_actual
    if not modulo:
        modulo = progreso.curso.modulos.order_by('numero').first()
        if not modulo:
            return (
                f"El curso *{progreso.curso.nombre}* no tiene módulos configurados.\n\n"
                f"{CIERRE_RETORNO_CURSO}"
            )
        progreso.modulo_actual = modulo
        progreso.save(update_fields=['modulo_actual'])

    encabezado = (
        f"📚 Reenvío de material — *{progreso.curso.nombre}*\n"
        f"Módulo {modulo.numero}: {modulo.titulo}\n\n"
    )

    if modulo_usa_pasos(modulo) and pasos_activos_qs(modulo).exists():
        paso_n = max(1, int(progreso.paso_actual_modulo or 1))
        try:
            bloque = entregar_bloque_secciones_desde_paso(progreso, modulo, paso_n)
        except Exception:
            logger.exception('[PQRS] Error reenviando pasos')
            bloque = None
        if bloque:
            # Prefijar encabezado dentro de MULTI_MSG si aplica
            if bloque.startswith('[MULTI_MSG]'):
                inner = bloque[len('[MULTI_MSG]'):]
                return '[MULTI_MSG]' + encabezado + '[SEP]' + inner
            return encabezado + bloque
        rem = mensaje_recordatorio_paso_actual(progreso, modulo)
        if rem:
            return encabezado + rem.replace('[MULTI_MSG]', '').replace('[SEP]', '\n\n')

    cuerpo = (modulo.contenido or '').strip() or (modulo.descripcion or '').strip()
    video = obtener_video_url(modulo) if modulo else None
    partes = [encabezado]
    if cuerpo:
        partes.append(cuerpo)
    if video:
        partes.append(f"[MEDIA:{video}]")
    partes.append(f"\nCuando termine, escriba *listo*.\n\n{CIERRE_RETORNO_CURSO}")
    return '\n'.join(partes).strip()


def ejecutar_correccion_datos(
    estudiante,
    *,
    campo: Optional[str] = None,
    valor_nuevo: Optional[str] = None,
) -> tuple[str, bool]:
    """
    Aplica corrección si hay campo+valor; si no, inicia el flujo guiado.
    Returns (mensaje_whatsapp, resolvio_caso).
    """
    from core.correccion_datos import iniciar_flujo_correccion

    campo_n = (campo or '').strip().lower()
    valor = (valor_nuevo or '').strip()

    if campo_n in CAMPOS_CORRECCION and valor:
        ok_msg = _aplicar_campo(estudiante, campo_n, valor)
        return ok_msg, True

    # Sin valor claro → menú de corrección (el estudiante termina el cambio)
    guia = iniciar_flujo_correccion(estudiante)
    return (
        f"{guia}\n\n"
        "Cuando termine la corrección, escriba *listo* para volver al curso."
    ), True


def _aplicar_campo(estudiante, campo: str, valor_nuevo: str) -> str:
    from core.correccion_datos import (
        _limpiar_flujo_correccion,
        _notificar_equipo_autocorreccion,
        _registrar_autocorreccion,
    )

    valor = valor_nuevo.strip()
    if campo == 'cedula':
        valor = ''.join(ch for ch in valor if ch.isdigit())
        if len(valor) < 6:
            return (
                "La cédula no parece válida. Envíe solo números (mínimo 6 dígitos) "
                "o escriba *corregir datos* para el menú guiado.\n\n"
                f"{CIERRE_RETORNO_CURSO}"
            )
    if len(valor) < 3:
        return (
            "Ese dato parece incompleto. Escriba *corregir datos* para el menú guiado.\n\n"
            f"{CIERRE_RETORNO_CURSO}"
        )

    anterior = getattr(estudiante, campo, '') or ''
    setattr(estudiante, campo, valor)
    try:
        estudiante.save(update_fields=[campo])
    except Exception:
        return (
            "No pude guardar ese dato. Si es cédula, verifique que no esté en otro perfil. "
            f"Escriba *corregir datos* o *ayuda*.\n\n{CIERRE_RETORNO_CURSO}"
        )

    _registrar_autocorreccion(estudiante, campo, anterior, valor)
    _notificar_equipo_autocorreccion(estudiante, campo, anterior, valor)
    _limpiar_flujo_correccion(estudiante)
    nombre = (estudiante.nombre or 'estudiante').split()[0]
    return (
        f"✅ Listo, {nombre}. Actualicé su *{campo}* correctamente.\n\n"
        f"{CIERRE_RETORNO_CURSO}"
    )


def ejecutar_accion_pqrs(
    estudiante,
    resultado: dict[str, Any],
) -> dict[str, Any]:
    """
    Ejecuta la acción declarada por el modelo y ajusta respuesta/escalar.
    Mutates and returns resultado.
    """
    accion = (resultado.get('accion') or 'ninguna').strip().lower()
    if accion not in ACCIONES_VALIDAS:
        accion = 'ninguna'
    resultado['accion'] = accion

    if accion == 'escalar':
        resultado['escalar'] = True
        return resultado

    if accion == 'explicar_progreso':
        resultado['respuesta_whatsapp'] = texto_explicar_progreso(estudiante)
        resultado['escalar'] = False
        resultado['nota_interna'] = (
            (resultado.get('nota_interna') or '') + ' | Acción: explicar_progreso'
        ).strip(' |')
        return resultado

    if accion == 'reenviar_modulo':
        resultado['respuesta_whatsapp'] = texto_reenviar_modulo(estudiante)
        resultado['escalar'] = False
        resultado['nota_interna'] = (
            (resultado.get('nota_interna') or '') + ' | Acción: reenviar_modulo'
        ).strip(' |')
        return resultado

    if accion == 'corregir_datos':
        msg, _ = ejecutar_correccion_datos(
            estudiante,
            campo=resultado.get('campo_correccion'),
            valor_nuevo=resultado.get('valor_nuevo'),
        )
        resultado['respuesta_whatsapp'] = msg
        resultado['escalar'] = False
        resultado['categoria'] = 'acceso'
        resultado['nota_interna'] = (
            (resultado.get('nota_interna') or '') + ' | Acción: corregir_datos'
        ).strip(' |')
        return resultado

    # ninguna: asegurar cierre con retorno al curso si no escala
    if not resultado.get('escalar'):
        resp = (resultado.get('respuesta_whatsapp') or '').strip()
        if CIERRE_RETORNO_CURSO not in resp and 'listo' not in resp.lower():
            resultado['respuesta_whatsapp'] = (
                resp + f"\n\n{CIERRE_RETORNO_CURSO}"
            ).strip()
    return resultado
