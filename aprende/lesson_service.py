"""Crear y editar lecciones del aula web (portal y /aprende/)."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db.models import Max

from core.bloques_modulo import crear_secciones_desde_titulos, parse_titulos_bloques_rapidos
from core.models import Curso, Modulo, SeccionModulo
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


def _contenido_con_bloques(contenido: str, bloques_raw: str) -> str:
    """Si no hay contenido pero sí bloques, arma borrador con los títulos."""
    contenido = (contenido or '').strip()
    if contenido:
        return contenido
    titulos = parse_titulos_bloques_rapidos(bloques_raw)
    if not titulos:
        return ''
    return (
        'Estructura del módulo (completar microcontenidos después):\n'
        + '\n'.join(f'• {t}' for t in titulos)
    )


def secciones_modulo_aula(modulo: Modulo):
    return (
        SeccionModulo.objects.filter(modulo=modulo, activa=True)
        .prefetch_related('pasos')
        .order_by('orden', 'id')
    )


def crear_modulo_aula(request, curso: Curso) -> tuple[Modulo | None, str | None]:
    campos = _campos_leccion_desde_post(request.POST)
    bloques_raw = request.POST.get('bloques_rapidos', '')
    campos['contenido'] = _contenido_con_bloques(campos['contenido'], bloques_raw)
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
    crear_secciones_desde_titulos(modulo, parse_titulos_bloques_rapidos(bloques_raw))
    guardar_archivo_modulo(request, modulo)
    return modulo, None


def actualizar_modulo_aula(request, modulo: Modulo) -> str | None:
    modulo.titulo = request.POST.get('titulo', modulo.titulo).strip()
    modulo.descripcion = request.POST.get('descripcion', '').strip()
    bloques_raw = request.POST.get('bloques_rapidos', '')
    contenido = request.POST.get('contenido', '').strip()
    modulo.contenido = _contenido_con_bloques(contenido, bloques_raw) or contenido
    modulo.video_url = request.POST.get('video_url', '').strip() or None
    modulo.archivo_pdf_url = request.POST.get('archivo_pdf_url', '').strip() or None

    try:
        validar_contenido_modulo(modulo.contenido, modulo)
        modulo.full_clean()
    except ValidationError as exc:
        return exc.messages[0] if getattr(exc, 'messages', None) else str(exc)

    modulo.save()
    # Solo agrega bloques nuevos (no borra los existentes).
    crear_secciones_desde_titulos(modulo, parse_titulos_bloques_rapidos(bloques_raw))
    guardar_archivo_modulo(request, modulo)
    return None
