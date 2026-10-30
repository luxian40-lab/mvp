"""Taxonomía territorial v0 — solo plagas y empleo (sin salud).

Legal/visión: empezar por familias de menor sensibilidad.
"""
from __future__ import annotations

# Tipos canónicos (familia.entidad.accion / detalle)
TAXONOMIA_V0: dict[str, dict] = {
    'agro.plaga.roya': {
        'familia': 'agro.plaga',
        'label': 'Roya / hongo foliar café-cacao',
        'keywords': (
            'roya', 'hemileia', 'hojas amarillas con polvo', 'polvo naranja',
        ),
    },
    'agro.plaga.broca': {
        'familia': 'agro.plaga',
        'label': 'Broca del café',
        'keywords': ('broca', 'broca del cafe', 'broca del café', 'perforacion grano', 'perforación grano'),
    },
    'agro.plaga.trips': {
        'familia': 'agro.plaga',
        'label': 'Trips',
        'keywords': ('trips', 'trip'),
    },
    'agro.plaga.acaro': {
        'familia': 'agro.plaga',
        'label': 'Ácaros',
        'keywords': ('acaro', 'ácaro', 'acaros', 'ácaros', 'arana roja', 'araña roja'),
    },
    'agro.plaga.gusano': {
        'familia': 'agro.plaga',
        'label': 'Gusanos / larvas',
        'keywords': ('gusano', 'gusanos', 'larva', 'larvas', 'cogollero', 'pasador'),
    },
    'agro.plaga.mancha': {
        'familia': 'agro.plaga',
        'label': 'Manchas / necrosis foliar',
        'keywords': ('mancha', 'manchas', 'necrosis', 'hoja quemada', 'hojas manchadas', 'antracnosis'),
    },
    'agro.plaga.general': {
        'familia': 'agro.plaga',
        'label': 'Plaga / enfermedad sin tipificar',
        'keywords': (
            'plaga', 'plagas', 'enfermedad', 'enfermedades', 'insecto', 'insectos',
            'fungicida', 'insecticida', 'bicho', 'bichos',
        ),
    },
    'empleo.barrera.transporte': {
        'familia': 'empleo.barrera',
        'label': 'Barrera de transporte / distancia',
        'keywords': (
            'no tengo transporte', 'sin transporte', 'queda lejos', 'muy lejos',
            'no puedo llegar', 'pasajes caros', 'no hay ruta',
        ),
    },
    'empleo.barrera.documentos': {
        'familia': 'empleo.barrera',
        'label': 'Barrera documental',
        'keywords': (
            'sin cedula', 'sin cédula', 'no tengo cedula', 'no tengo cédula',
            'no tengo documentos', 'papeles incompletos',
            'falta documento', 'no tengo certificado',
        ),
    },
    'empleo.barrera.horario': {
        'familia': 'empleo.barrera',
        'label': 'Barrera de horario / cuidado',
        'keywords': (
            'no puedo en la manana', 'no puedo en la mañana', 'cuido a', 'horario no me sirve',
            'solo fines de semana', 'trabajo de dia', 'trabajo de día',
        ),
    },
    'empleo.barrera.general': {
        'familia': 'empleo.barrera',
        'label': 'Barrera de empleo genérica',
        'keywords': (
            'no consigo trabajo', 'busco empleo', 'busco trabajo', 'no me contratan',
            'dificil conseguir empleo', 'difícil conseguir empleo', 'sin empleo',
        ),
    },
}

# Tipos bloqueados en v0 (nunca clasificar / nunca persistir)
TIPOS_BLOQUEADOS_V0 = frozenset({
    'salud',
    'salud.sintoma',
    'salud.sintoma.diarrea',
    'salud.cluster',
})

# Ejemplos etiquetados a mano para tests / precisión v0 (texto → tipo esperado o None)
EJEMPLOS_ETIQUETADOS: list[tuple[str, str | None]] = [
    ('tengo roya en el cafetal', 'agro.plaga.roya'),
    ('la broca me está comiendo el grano', 'agro.plaga.broca'),
    ('vi trips en el aguacate', 'agro.plaga.trips'),
    ('hay ácaros en las hojas', 'agro.plaga.acaro'),
    ('aparecieron gusanos en el maíz', 'agro.plaga.gusano'),
    ('las hojas tienen manchas negras', 'agro.plaga.mancha'),
    ('qué plaga puede ser esta', 'agro.plaga.general'),
    ('necesito un insecticida para plagas', 'agro.plaga.general'),
    ('no tengo transporte para ir a la entrevista', 'empleo.barrera.transporte'),
    ('me queda muy lejos el trabajo', 'empleo.barrera.transporte'),
    ('no tengo cédula actualizada', 'empleo.barrera.documentos'),
    ('cuido a mi mamá y el horario no me sirve', 'empleo.barrera.horario'),
    ('busco empleo en la zona', 'empleo.barrera.general'),
    ('no consigo trabajo desde enero', 'empleo.barrera.general'),
    # Negativos / no clasificar
    ('hola nat buenos días', None),
    ('cuánto cuesta el abono 15-15-15', None),
    ('listo', None),
    ('tengo diarrea desde ayer', None),  # salud bloqueada
    ('síntomas de infección intestinal', None),
]
