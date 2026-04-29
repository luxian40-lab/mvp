from __future__ import annotations

import re

from django.core.management.base import BaseCommand

from core.models import Curso


PREGUNTA_DIAGNOSTICO_RECORTADA = (
    "¿Cómo podría usted determinar si el mal estado de sus plantas se debe a la Diatraea?"
)


def _corregir_texto_preguntas(texto: str) -> tuple[str, int]:
    if not texto:
        return texto, 0
    original = texto

    # Corrección A1: typo fijo en encabezado/preguntas.
    texto = re.sub(r"\bACCI[ÓO]N\b", "ACCIONA", texto, flags=re.IGNORECASE)
    texto = re.sub(
        r"OBSERVA\s*,\s*CUANTIFICA\s*Y\s*ACCIONA",
        "ACCIONA",
        texto,
        flags=re.IGNORECASE,
    )

    # Corrección A2: recorte de pregunta para que se alinee con módulos 1-3.
    patrones = [
        r"¿Cómo[^?]*mal estado[^?]*Diatraea[^?]*\?",
        r"¿Cómo[^?]*determinar[^?]*Diatraea[^?]*\?",
    ]
    for p in patrones:
        texto = re.sub(p, PREGUNTA_DIAGNOSTICO_RECORTADA, texto, flags=re.IGNORECASE)

    # Si la pregunta quedó con parte de control, se limpia explícitamente.
    texto = re.sub(
        r"(y|e)\s+qué\s+(medida|acción|accion)\s+de\s+control[^?.!]*[?.!]",
        "",
        texto,
        flags=re.IGNORECASE,
    )

    cambios = 1 if texto != original else 0
    return texto, cambios


class Command(BaseCommand):
    help = "Corrige preguntas_ejemplo_ia en cursos Diatraea (ACCIONA + pregunta recortada módulos 1-3)."

    def handle(self, *args, **options):
        cursos = Curso.objects.filter(
            preguntas_ejemplo_ia__isnull=False
        ).exclude(preguntas_ejemplo_ia="")

        tocados = 0
        for curso in cursos:
            texto = curso.preguntas_ejemplo_ia or ""
            if "diatraea" not in texto.lower() and "diatraea" not in (curso.nombre or "").lower():
                continue
            nuevo, cambios = _corregir_texto_preguntas(texto)
            if cambios:
                curso.preguntas_ejemplo_ia = nuevo
                curso.save(update_fields=["preguntas_ejemplo_ia"])
                tocados += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Curso actualizado: id={curso.id} nombre={curso.nombre}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Correccion Diatraea aplicada. Cursos modificados: {tocados}"
            )
        )
