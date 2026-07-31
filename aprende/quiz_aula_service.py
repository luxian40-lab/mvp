"""Quiz web del aula (PreguntaModulo) — práctica LMS, no reemplaza *listo* WhatsApp."""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from aprende.models import IntentoQuizModulo
from core.models import Estudiante, Modulo, PreguntaModulo


def preguntas_activas(modulo: Modulo):
    return list(
        PreguntaModulo.objects.filter(modulo=modulo, activa=True).order_by('id')
    )


def opciones_pregunta(pregunta: PreguntaModulo) -> list[tuple[str, str]]:
    opts: list[tuple[str, str]] = [('A', pregunta.opcion_a), ('B', pregunta.opcion_b)]
    if (pregunta.opcion_c or '').strip():
        opts.append(('C', pregunta.opcion_c))
    if (pregunta.opcion_d or '').strip():
        opts.append(('D', pregunta.opcion_d))
    return opts


@dataclass
class ResultadoQuiz:
    intento: IntentoQuizModulo
    detalle: list[dict]


def calificar_desde_post(estudiante: Estudiante, modulo: Modulo, post) -> ResultadoQuiz | str:
    preguntas = preguntas_activas(modulo)
    if not preguntas:
        return 'Este módulo no tiene preguntas de práctica.'

    detalle = []
    correctas = 0
    mapa: dict[str, str] = {}
    for p in preguntas:
        raw = (post.get(f'q_{p.id}') or '').strip().upper()
        if raw not in ('A', 'B', 'C', 'D'):
            return 'Responde todas las preguntas antes de enviar.'
        ok = raw == (p.respuesta_correcta or '').upper()
        if ok:
            correctas += 1
        mapa[str(p.id)] = raw
        detalle.append({
            'pregunta': p,
            'respuesta': raw,
            'correcta': ok,
            'letra_ok': p.respuesta_correcta,
            'explicacion': (p.explicacion or '').strip(),
        })

    total = len(preguntas)
    aprobado = correctas >= max(1, (total * 60 + 99) // 100)  # ≥60%

    with transaction.atomic():
        intento, _ = IntentoQuizModulo.objects.update_or_create(
            estudiante=estudiante,
            modulo=modulo,
            defaults={
                'respuestas': mapa,
                'correctas': correctas,
                'total': total,
                'aprobado': aprobado,
            },
        )
    return ResultadoQuiz(intento=intento, detalle=detalle)


def intento_previo(estudiante: Estudiante, modulo: Modulo) -> IntentoQuizModulo | None:
    return (
        IntentoQuizModulo.objects.filter(estudiante=estudiante, modulo=modulo)
        .order_by('-fecha')
        .first()
    )
