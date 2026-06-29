"""Subida de documentos del estudiante en el aula."""

from __future__ import annotations

from django.core.exceptions import ValidationError

from core.models import Curso, Estudiante, Modulo

from .acceso_modulos import modulo_accesible_aula
from .archivos_aula import validar_archivo_entrega
from .models import DocumentoEstudianteAula
from .tarea_service import estudiante_inscrito_en_curso


def guardar_documento_aula(
    request,
    estudiante: Estudiante,
    curso: Curso,
    modulo: Modulo | None = None,
) -> tuple[DocumentoEstudianteAula | None, str | None]:
    if not estudiante_inscrito_en_curso(estudiante, curso):
        return None, 'No estás inscrito en este curso.'
    if modulo and modulo.curso_id != curso.pk:
        return None, 'El módulo no pertenece a este curso.'
    if modulo and not modulo_accesible_aula(estudiante, modulo):
        return None, 'Este módulo aún no está disponible para ti.'

    titulo = request.POST.get('titulo', '').strip()
    if not titulo:
        return None, 'Indica un título para el documento.'
    archivo = request.FILES.get('archivo')
    try:
        validar_archivo_entrega(archivo)
    except ValidationError as exc:
        return None, exc.messages[0]

    doc = DocumentoEstudianteAula.objects.create(
        estudiante=estudiante,
        curso=curso,
        modulo=modulo,
        titulo=titulo[:200],
        descripcion=request.POST.get('descripcion', '').strip(),
        archivo=archivo,
        nombre_archivo=archivo.name,
    )
    return doc, None
