"""Opciones de campos de modelos. No importa nada de core: los modelos no cargan lógica de negocio por esto."""

PLAN_CURSO_ASESOR = 'curso_asesor'
PLAN_DOS_CURSOS = 'dos_cursos'
PLAN_ASESOR_60 = 'asesor_60'

PLAN_CHOICES = [
    (PLAN_CURSO_ASESOR, 'OP1 — 1 curso al mes + asesor (60 preguntas)'),
    (PLAN_DOS_CURSOS, 'OP2 — 2 cursos al mes + asesor (120 preguntas)'),
    (PLAN_ASESOR_60, 'OP3 — asesor, 60 preguntas al mes'),
]
