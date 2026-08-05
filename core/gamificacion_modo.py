"""Modo de gamificación por organización (puntos vs calificación 1–5 con ranking)."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

MODO_DESACTIVADO = 'desactivado'
MODO_PUNTOS = 'puntos'
MODO_CALIFICACION = 'calificacion'

MODO_GAMIFICACION_CHOICES = [
    (MODO_DESACTIVADO, 'Desactivada'),
    (MODO_PUNTOS, 'Puntos (ranking por puntos)'),
    (MODO_CALIFICACION, 'Calificación 1–5 (ranking por promedio)'),
]


def get_modo_gamificacion(cliente) -> str:
    if not cliente:
        return MODO_PUNTOS
    modo = (getattr(cliente, 'modo_gamificacion', None) or '').strip()
    if modo in {MODO_DESACTIVADO, MODO_PUNTOS, MODO_CALIFICACION}:
        return modo
    if getattr(cliente, 'usar_gamificacion', True):
        return MODO_PUNTOS
    return MODO_DESACTIVADO


def gamificacion_activa(cliente) -> bool:
    return get_modo_gamificacion(cliente) != MODO_DESACTIVADO


def modo_usa_puntos(cliente) -> bool:
    return get_modo_gamificacion(cliente) == MODO_PUNTOS


def modo_usa_calificacion(cliente) -> bool:
    return get_modo_gamificacion(cliente) == MODO_CALIFICACION


def sincronizar_usar_gamificacion(cliente) -> None:
    if cliente is None:
        return
    cliente.usar_gamificacion = gamificacion_activa(cliente)


def formatear_nota(nota: float | Decimal) -> str:
    d = Decimal(str(nota)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    texto = format(d, 'f').rstrip('0').rstrip('.')
    return texto or '0'


def _peso_cliente_por_tipo(cliente, tipo: str) -> Decimal:
    if not cliente:
        return Decimal('1')
    if tipo == 'pregunta_abierta':
        return Decimal(str(getattr(cliente, 'peso_gamificacion_abierta', 1) or 1))
    if tipo == 'reto':
        return Decimal(str(getattr(cliente, 'peso_gamificacion_reto', 1) or 1))
    return Decimal('1')


def registrar_nota_gamificacion(
    estudiante,
    nota: float | Decimal,
    tipo: str,
    *,
    curso=None,
    modulo=None,
    detalle: str = '',
    peso: Decimal | None = None,
) -> None:
    """Guarda una nota para sumarla al ranking por promedio ponderado."""
    from core.gamificacion import EvaluacionNotaGamificacion

    valor = Decimal(str(nota)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    valor = max(Decimal('1'), min(Decimal('5'), valor))
    cliente = getattr(estudiante, 'cliente', None)
    peso_final = peso if peso is not None else _peso_cliente_por_tipo(cliente, tipo)

    EvaluacionNotaGamificacion.objects.create(
        estudiante=estudiante,
        curso=curso,
        modulo=modulo,
        nota=valor,
        peso=peso_final,
        tipo=tipo,
        detalle=(detalle or '')[:200],
    )


def resumen_calificaciones_estudiante(estudiante, curso_id: int | None = None) -> dict[str, Any]:
    """Suma ponderada, total de pesos y promedio 1–5 del estudiante."""
    from django.db.models import Count, F, Sum

    from core.gamificacion import EvaluacionNotaGamificacion

    qs = EvaluacionNotaGamificacion.objects.filter(estudiante=estudiante)
    if curso_id:
        qs = qs.filter(curso_id=curso_id)

    agg = qs.aggregate(
        suma_ponderada=Sum(F('nota') * F('peso')),
        suma_pesos=Sum('peso'),
        cantidad=Count('id'),
    )
    suma_pesos = agg['suma_pesos'] or Decimal('0')
    suma_ponderada = agg['suma_ponderada'] or Decimal('0')
    promedio = (suma_ponderada / suma_pesos) if suma_pesos else None

    return {
        'cantidad': agg['cantidad'] or 0,
        'suma_ponderada': suma_ponderada,
        'suma_pesos': suma_pesos,
        'promedio': promedio,
    }


def ranking_calificaciones_cliente(cliente, curso_id: int | None = None, limite: int = 100) -> list[dict]:
    """
    Ranking por promedio ponderado de notas (mayor nota = mejor posición).
    Cada fila: estudiante_id, nombre, promedio, cantidad_evaluaciones, suma_ponderada.
    """
    from django.db.models import Count, F, Sum

    from core.gamificacion import EvaluacionNotaGamificacion

    qs = EvaluacionNotaGamificacion.objects.filter(
        estudiante__cliente=cliente,
        estudiante__activo=True,
    ).select_related('estudiante')
    if curso_id:
        qs = qs.filter(curso_id=curso_id)

    filas = (
        qs.values('estudiante_id', 'estudiante__nombre')
        .annotate(
            suma_ponderada=Sum(F('nota') * F('peso')),
            suma_pesos=Sum('peso'),
            cantidad=Count('id'),
        )
        .filter(suma_pesos__gt=0)
        .order_by('-suma_ponderada', '-cantidad', 'estudiante__nombre')[:limite]
    )

    ranking = []
    for pos, row in enumerate(filas, start=1):
        promedio = row['suma_ponderada'] / row['suma_pesos']
        ranking.append({
            'posicion': pos,
            'estudiante_id': row['estudiante_id'],
            'nombre': row['estudiante__nombre'],
            'promedio': promedio.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
            'cantidad': row['cantidad'],
            'suma_ponderada': row['suma_ponderada'],
            'suma_pesos': row['suma_pesos'],
        })
    return ranking


def gamificacion_otorga_puntos(cliente, curso=None) -> bool:
    if curso is not None and getattr(curso, 'es_modo_clases', lambda: False)():
        return False
    if not modo_usa_puntos(cliente):
        return False
    if curso is not None and getattr(curso, 'usar_gamificacion', False):
        return True
    return gamificacion_activa(cliente)


def linea_resultado_reto_whatsapp(
    *,
    modo: str,
    puntaje_10: int | None,
    nota_5: float | None,
    puntos_ganados: int | None,
    puntos_totales: int | None,
    promedio_notas: Decimal | None,
    barra_progreso: str,
    porcentaje: int,
) -> str:
    if modo == MODO_CALIFICACION and nota_5 is not None:
        extra = ''
        if promedio_notas is not None:
            extra = f"\n📊 *Promedio acumulado:* {formatear_nota(promedio_notas)}/5"
        return (
            f"📋 *Nota:* {formatear_nota(nota_5)}/5{extra}\n"
            f"{barra_progreso} {porcentaje}%"
        )
    if puntos_ganados is not None and puntos_totales is not None:
        return (
            f"💰 *+{puntos_ganados} puntos* → Total: *{puntos_totales} pts*\n"
            f"{barra_progreso} {porcentaje}%"
        )
    if puntaje_10 is not None:
        return f"📋 *Puntaje reto:* {puntaje_10}/10\n{barra_progreso} {porcentaje}%"
    return f"{barra_progreso} {porcentaje}%"


def construir_mensaje_evaluacion_reto(
    estudiante,
    progreso,
    puntaje_o_nota,
    feedback: str,
    nombre_tutor: str,
) -> str:
    from core.response_templates import _barra_progreso

    cliente = getattr(estudiante, 'cliente', None)
    modo = get_modo_gamificacion(cliente)
    curso = getattr(progreso, 'curso', None) if progreso else None
    curso_id = curso.id if curso else None
    porcentaje = int(progreso.porcentaje_avance()) if progreso else 0
    barra = _barra_progreso(porcentaje)

    msg = f"📋 *{nombre_tutor}*\n\n{feedback}\n\n"

    if modo == MODO_CALIFICACION:
        nota = float(puntaje_o_nota)
        registrar_nota_gamificacion(
            estudiante,
            nota,
            'reto',
            curso=curso,
            detalle='Reto facilitadora',
        )
        resumen = resumen_calificaciones_estudiante(estudiante, curso_id)
        msg += linea_resultado_reto_whatsapp(
            modo=modo,
            puntaje_10=None,
            nota_5=nota,
            puntos_ganados=None,
            puntos_totales=None,
            promedio_notas=resumen.get('promedio'),
            barra_progreso=barra,
            porcentaje=porcentaje,
        )
        return msg

    if gamificacion_otorga_puntos(cliente, curso):
        from core.gamificacion import PerfilGamificacion

        puntaje_10 = int(puntaje_o_nota)
        perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
        puntos_reto = puntaje_10 * 5
        perfil.agregar_puntos(puntos_reto, f"Reto evaluado: {puntaje_10}/10")
        perfil.refresh_from_db()
        msg += linea_resultado_reto_whatsapp(
            modo=MODO_PUNTOS,
            puntaje_10=puntaje_10,
            nota_5=None,
            puntos_ganados=puntos_reto,
            puntos_totales=perfil.puntos_totales,
            promedio_notas=None,
            barra_progreso=barra,
            porcentaje=porcentaje,
        )
        return msg

    msg += linea_resultado_reto_whatsapp(
        modo=modo,
        puntaje_10=int(puntaje_o_nota) if puntaje_o_nota else None,
        nota_5=None,
        puntos_ganados=None,
        puntos_totales=None,
        promedio_notas=None,
        barra_progreso=barra,
        porcentaje=porcentaje,
    )
    return msg

