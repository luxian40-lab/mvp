"""Crear tareas, recibir entregas y calificar."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models import Curso, ProgresoEstudiante

from .archivos_aula import validar_archivo_entrega
from .models import EntregaTarea, TareaCurso


def estudiante_inscrito_en_curso(estudiante, curso: Curso) -> bool:
    return ProgresoEstudiante.objects.filter(estudiante=estudiante, curso=curso).exists()


def crear_tarea(request, curso: Curso) -> tuple[TareaCurso | None, str | None]:
    titulo = request.POST.get('titulo', '').strip()
    if not titulo:
        return None, 'El título de la tarea es obligatorio.'
    modulo_id = request.POST.get('modulo') or None
    modulo = None
    if modulo_id:
        modulo = curso.modulos.filter(pk=modulo_id).first()
    fecha_limite = None
    raw_fecha = request.POST.get('fecha_limite', '').strip()
    if raw_fecha:
        from datetime import datetime, time

        from django.utils.dateparse import parse_date, parse_datetime

        fecha_limite = parse_datetime(raw_fecha)
        if not fecha_limite:
            d = parse_date(raw_fecha)
            if d:
                fecha_limite = timezone.make_aware(datetime.combine(d, time(23, 59, 59)))
    tarea = TareaCurso.objects.create(
        curso=curso,
        modulo=modulo,
        titulo=titulo,
        instrucciones=request.POST.get('instrucciones', '').strip(),
        fecha_limite=fecha_limite,
        activa=True,
    )
    return tarea, None


def guardar_entrega(request, tarea: TareaCurso, estudiante) -> tuple[EntregaTarea | None, str | None]:
    archivo = request.FILES.get('archivo')
    entrega_prev = EntregaTarea.objects.filter(tarea=tarea, estudiante=estudiante).first()
    if not archivo and not entrega_prev:
        return None, 'Debes adjuntar un archivo.'
    if archivo:
        try:
            validar_archivo_entrega(archivo)
        except ValidationError as exc:
            return None, exc.messages[0]

    entrega, _ = EntregaTarea.objects.get_or_create(
        tarea=tarea,
        estudiante=estudiante,
        defaults={'nombre_archivo': archivo.name if archivo else ''},
    )
    if archivo:
        if entrega.archivo:
            entrega.archivo.delete(save=False)
        entrega.archivo = archivo
        entrega.nombre_archivo = archivo.name
    entrega.comentario_estudiante = request.POST.get('comentario', '').strip()
    if not entrega_prev or archivo:
        entrega.nota = None
        entrega.comentario_profesor = ''
        entrega.fecha_calificacion = None
        entrega.calificado_por = None
    entrega.save()
    return entrega, None


def calificar_entrega(request, entrega: EntregaTarea) -> str | None:
    raw_nota = request.POST.get('nota', '').strip()
    if not raw_nota:
        return 'Indica una nota del 1 al 5.'
    try:
        nota = int(raw_nota)
    except ValueError:
        return 'La nota debe ser un número del 1 al 5.'
    if not 1 <= nota <= 5:
        return 'La nota debe estar entre 1 y 5.'
    entrega.nota = nota
    entrega.comentario_profesor = request.POST.get('comentario_profesor', '').strip()
    entrega.fecha_calificacion = timezone.now()
    pu = getattr(request, 'portal_usuario', None)
    entrega.calificado_por = pu.user if pu else None
    entrega.save()
    return None
