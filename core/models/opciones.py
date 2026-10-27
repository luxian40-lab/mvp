"""Opciones de campos de modelos y reglas que solo leen esos campos. No importa nada de core: los modelos no cargan lógica de negocio por esto."""

PLAN_CURSO_ASESOR = 'curso_asesor'
PLAN_DOS_CURSOS = 'dos_cursos'
PLAN_ASESOR_60 = 'asesor_60'

PLAN_CHOICES = [
    (PLAN_CURSO_ASESOR, 'OP1 — 1 curso al mes + asesor (60 preguntas)'),
    (PLAN_DOS_CURSOS, 'OP2 — 2 cursos al mes + asesor (120 preguntas)'),
    (PLAN_ASESOR_60, 'OP3 — asesor, 60 preguntas al mes'),
]


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


def sincronizar_usar_gamificacion(cliente) -> None:
    if cliente is None:
        return
    cliente.usar_gamificacion = gamificacion_activa(cliente)
