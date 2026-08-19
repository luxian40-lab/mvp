"""Crear y editar lecciones del aula web (portal y /aprende/)."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db.models import Max

from core.bloques_modulo import crear_secciones_desde_titulos, parse_titulos_bloques_rapidos
from core.models import Curso, Modulo, SeccionModulo
from core.models_extras import ArchivoModulo
from core.module_steps import validar_contenido_modulo


def _infer_tipo_url(url: str) -> str:
    u = url.lower()
    if 'youtube.com' in u or 'youtu.be' in u or 'vimeo.com' in u:
        return 'video'
    if u.endswith('.pdf') or '.pdf' in u.split('?')[0]:
        return 'pdf'
    if any(u.endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp')):
        return 'imagen'
    if any(u.endswith(ext) for ext in ('.mp3', '.wav', '.ogg', '.m4a')):
        return 'audio'
    return 'pdf'


def _parse_linea_recurso_externo(line: str) -> tuple[str, str, str] | None:
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    if '|' in line:
        parts = [p.strip() for p in line.split('|', 2)]
        if len(parts) == 3:
            tipo, url, titulo = parts
            if tipo not in dict(ArchivoModulo.TIPOS):
                tipo = _infer_tipo_url(url)
            return tipo, url, titulo[:200] or url[:200]
        if len(parts) == 2:
            url, titulo = parts
            return _infer_tipo_url(url), url, titulo[:200] or url[:200]
    return _infer_tipo_url(line), line, line[:200]


def _orden_max_archivos(modulo: Modulo) -> int:
    return (
        ArchivoModulo.objects.filter(modulo=modulo)
        .aggregate(m=Max('orden'))['m']
        or 0
    )


def guardar_recursos_externos_modulo(post, modulo: Modulo) -> str | None:
    """Agrega enlaces (YouTube, PDF, etc.) como ArchivoModulo vía bulk_create."""
    raw = post.get('recursos_externos', '')
    parsed: list[tuple[str, str, str]] = []
    for line in raw.splitlines():
        item = _parse_linea_recurso_externo(line)
        if item:
            parsed.append(item)
    if not parsed:
        return None
    max_orden = _orden_max_archivos(modulo)
    to_create = [
        ArchivoModulo(
            modulo=modulo,
            tipo=tipo,
            titulo=titulo,
            url_externa=url,
            orden=max_orden + i + 1,
            activo=True,
        )
        for i, (tipo, url, titulo) in enumerate(parsed)
    ]
    ArchivoModulo.objects.bulk_create(to_create)
    return None


def eliminar_archivos_modulo(post, modulo: Modulo) -> None:
    ids = post.getlist('eliminar_archivo')
    if ids:
        ArchivoModulo.objects.filter(modulo=modulo, pk__in=ids).update(activo=False)


def guardar_archivos_subidos_modulo(request, modulo: Modulo) -> str | None:
    files = request.FILES.getlist('archivo_subir')
    if not files:
        return None
    tipo = request.POST.get('tipo_archivo', 'pdf')
    if tipo not in dict(ArchivoModulo.TIPOS):
        tipo = 'pdf'
    titulo_base = request.POST.get('titulo_archivo', '').strip()
    from aprende.archivos_aula import validar_archivo_clase_profesor

    max_orden = _orden_max_archivos(modulo)
    for i, archivo in enumerate(files):
        try:
            validar_archivo_clase_profesor(archivo, tipo_hint=tipo)
        except ValidationError as exc:
            return exc.messages[0]
        titulo = titulo_base or archivo.name
        if len(files) > 1 and titulo_base:
            titulo = f'{titulo_base} ({i + 1})'
        ArchivoModulo.objects.create(
            modulo=modulo,
            tipo=tipo,
            titulo=titulo[:200],
            descripcion=request.POST.get('descripcion_archivo', '')[:500],
            archivo=archivo,
            orden=max_orden + i + 1,
        )
    return None


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


def _aplicar_adjuntos_modulo(request, modulo: Modulo) -> str | None:
    eliminar_archivos_modulo(request.POST, modulo)
    err = guardar_recursos_externos_modulo(request.POST, modulo)
    if err:
        return err
    return guardar_archivos_subidos_modulo(request, modulo)


def crear_modulo_aula(request, curso: Curso) -> tuple[Modulo | None, str | None]:
    campos = _campos_leccion_desde_post(request.POST)
    bloques_raw = request.POST.get('bloques_rapidos', '')
    campos['contenido'] = _contenido_con_bloques(campos['contenido'], bloques_raw)
    try:
        validar_contenido_modulo(campos['contenido'], None)
    except ValidationError as exc:
        return None, exc.messages[0]

    files = request.FILES.getlist('archivo_subir')
    if files:
        from aprende.archivos_aula import validar_archivo_clase_profesor

        tipo = request.POST.get('tipo_archivo', 'pdf')
        for archivo in files:
            try:
                validar_archivo_clase_profesor(archivo, tipo_hint=tipo)
            except ValidationError as exc:
                return None, exc.messages[0]

    max_num = Modulo.objects.filter(curso=curso).aggregate(m=Max('numero'))['m'] or 0
    modulo = Modulo.objects.create(
        curso=curso,
        numero=int(max_num) + 1,
        **campos,
    )
    crear_secciones_desde_titulos(modulo, parse_titulos_bloques_rapidos(bloques_raw))
    return modulo, _aplicar_adjuntos_modulo(request, modulo)


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
    crear_secciones_desde_titulos(modulo, parse_titulos_bloques_rapidos(bloques_raw))
    return _aplicar_adjuntos_modulo(request, modulo)
