"""Crear tareas, recibir entregas y calificar."""

from __future__ import annotations

from datetime import datetime, time

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from core.models import Curso, ProgresoEstudiante

from .archivos_aula import validar_archivo_entrega
from .models import EntregaTarea, TareaCurso


def estudiante_inscrito_en_curso(estudiante, curso: Curso) -> bool:
    return ProgresoEstudiante.objects.filter(estudiante=estudiante, curso=curso).exists()


def _parse_fecha_limite(raw_fecha: str):
    raw_fecha = (raw_fecha or '').strip()
    if not raw_fecha:
        return None
    fecha_limite = parse_datetime(raw_fecha)
    if not fecha_limite:
        d = parse_date(raw_fecha)
        if d:
            fecha_limite = timezone.make_aware(datetime.combine(d, time(23, 59, 59)))
    return fecha_limite


def crear_tarea(request, curso: Curso) -> tuple[TareaCurso | None, str | None]:
    titulo = request.POST.get('titulo', '').strip()
    if not titulo:
        return None, 'El título de la tarea es obligatorio.'
    modulo_id = request.POST.get('modulo') or None
    modulo = curso.modulos.filter(pk=modulo_id).first() if modulo_id else None
    tarea = TareaCurso.objects.create(
        curso=curso,
        modulo=modulo,
        titulo=titulo,
        instrucciones=request.POST.get('instrucciones', '').strip(),
        fecha_limite=_parse_fecha_limite(request.POST.get('fecha_limite', '')),
        activa=True,
    )
    return tarea, None


def actualizar_tarea(request, tarea: TareaCurso) -> str | None:
    titulo = request.POST.get('titulo', '').strip()
    if not titulo:
        return 'El título de la tarea es obligatorio.'
    curso = tarea.curso
    modulo_id = request.POST.get('modulo') or None
    tarea.titulo = titulo
    tarea.instrucciones = request.POST.get('instrucciones', '').strip()
    tarea.modulo = curso.modulos.filter(pk=modulo_id).first() if modulo_id else None
    tarea.fecha_limite = _parse_fecha_limite(request.POST.get('fecha_limite', ''))
    tarea.activa = request.POST.get('activa', 'on') == 'on'
    tarea.save()
    return None


def eliminar_tarea(tarea: TareaCurso) -> tuple[bool, str]:
    if tarea.entregas.exists():
        tarea.activa = False
        tarea.save(update_fields=['activa'])
        return False, 'La tarea tiene entregas; se desactivó en lugar de borrarla.'
    tarea.delete()
    return True, 'Tarea eliminada.'


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


def guardar_respuesta_post_calificacion(
    request,
    entrega: EntregaTarea,
) -> str | None:
    """Permite al estudiante comentar tras ver la nota del profesor (sin cambiar la entrega)."""
    if not entrega.calificada:
        return 'La tarea aún no está calificada.'
    texto = (request.POST.get('respuesta') or request.POST.get('comentario') or '').strip()
    if not texto:
        return 'Escribe un comentario para tu profesor.'
    if len(texto) > 2000:
        return 'El comentario es demasiado largo (máx. 2000 caracteres).'
    entrega.respuesta_estudiante = texto
    entrega.fecha_respuesta_estudiante = timezone.now()
    entrega.save(update_fields=['respuesta_estudiante', 'fecha_respuesta_estudiante'])
    return None


def _parse_nota(raw: str) -> tuple[int | None, str | None]:
    raw = (raw or '').strip()
    if not raw:
        return None, None
    try:
        nota = int(raw)
    except ValueError:
        return None, 'La nota debe ser un número del 1 al 5.'
    if not 1 <= nota <= 5:
        return None, 'La nota debe estar entre 1 y 5.'
    return nota, None


def _aplicar_calificacion_entrega(
    entrega: EntregaTarea,
    nota: int,
    comentario: str,
    calificador,
) -> None:
    entrega.nota = nota
    entrega.comentario_profesor = comentario
    entrega.fecha_calificacion = timezone.now()
    entrega.calificado_por = calificador
    entrega.save()
    from .calificacion_aula_service import sincronizar_nota_tarea_entrega

    sincronizar_nota_tarea_entrega(entrega)


def calificar_entrega(request, entrega: EntregaTarea) -> str | None:
    nota, err = _parse_nota(request.POST.get('nota', ''))
    if err:
        return err
    if nota is None:
        return 'Indica una nota del 1 al 5.'
    pu = getattr(request, 'portal_usuario', None)
    _aplicar_calificacion_entrega(
        entrega,
        nota,
        request.POST.get('comentario_profesor', '').strip(),
        pu.user if pu else None,
    )
    return None


def calificar_entregas_lote(request, entregas) -> tuple[int, str | None]:
    """Califica varias entregas en un solo envío (nota_<id>, comentario_<id>)."""
    guardadas = 0
    pu = getattr(request, 'portal_usuario', None)
    calificador = pu.user if pu else None
    for entrega in entregas:
        raw = request.POST.get(f'nota_{entrega.id}', '')
        nota, err = _parse_nota(raw)
        if err:
            return guardadas, err
        if nota is None:
            continue
        _aplicar_calificacion_entrega(
            entrega,
            nota,
            request.POST.get(f'comentario_{entrega.id}', '').strip(),
            calificador,
        )
        guardadas += 1
    if guardadas == 0:
        return 0, 'Indica al menos una nota para guardar.'
    return guardadas, None
