"""Crear y editar lecciones del aula web (portal y /aprende/)."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db.models import Max

from core.models import Curso, Modulo
from core.models_extras import ArchivoModulo
from core.module_steps import validar_contenido_modulo


def guardar_archivo_modulo(request, modulo: Modulo) -> None:
    archivo = request.FILES.get('archivo_subir')
    if not archivo:
        return
    tipo = request.POST.get('tipo_archivo', 'pdf')
    if tipo not in dict(ArchivoModulo.TIPOS):
        tipo = 'pdf'
    ArchivoModulo.objects.create(
        modulo=modulo,
        tipo=tipo,
        titulo=request.POST.get('titulo_archivo', archivo.name)[:200],
        descripcion=request.POST.get('descripcion_archivo', '')[:500],
        archivo=archivo,
    )


def _campos_leccion_desde_post(post) -> dict:
    return {
        'titulo': post.get('titulo', '').strip() or 'Nueva lección',
        'descripcion': post.get('descripcion', '').strip(),
        'contenido': post.get('contenido', '').strip(),
        'video_url': post.get('video_url', '').strip() or None,
        'archivo_pdf_url': post.get('archivo_pdf_url', '').strip() or None,
    }


def crear_modulo_aula(request, curso: Curso) -> tuple[Modulo | None, str | None]:
    campos = _campos_leccion_desde_post(request.POST)
    try:
        validar_contenido_modulo(campos['contenido'], None)
    except ValidationError as exc:
        return None, exc.messages[0]

    max_num = Modulo.objects.filter(curso=curso).aggregate(m=Max('numero'))['m'] or 0
    modulo = Modulo.objects.create(
        curso=curso,
        numero=int(max_num) + 1,
        **campos,
    )
    guardar_archivo_modulo(request, modulo)
    return modulo, None


def actualizar_modulo_aula(request, modulo: Modulo) -> str | None:
    modulo.titulo = request.POST.get('titulo', modulo.titulo).strip()
    modulo.descripcion = request.POST.get('descripcion', '').strip()
    modulo.contenido = request.POST.get('contenido', '').strip()
    modulo.video_url = request.POST.get('video_url', '').strip() or None
    modulo.archivo_pdf_url = request.POST.get('archivo_pdf_url', '').strip() or None

    try:
        validar_contenido_modulo(modulo.contenido, modulo)
        modulo.full_clean()
    except ValidationError as exc:
        return exc.messages[0] if getattr(exc, 'messages', None) else str(exc)

    modulo.save()
    guardar_archivo_modulo(request, modulo)
    return None
