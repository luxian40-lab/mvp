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


def url_publica_archivo_modulo(archivo: ArchivoModulo) -> str | None:
    if archivo.url_externa:
        return archivo.url_externa
    if archivo.archivo:
        return archivo.archivo.url
    return None


def _orden_max_archivos(modulo: Modulo) -> int:
    return (
        ArchivoModulo.objects.filter(modulo=modulo)
        .aggregate(m=Max('orden'))['m']
        or 0
    )


def migrar_recursos_legacy_modulo(modulo: Modulo) -> bool:
    """Mueve video_url / archivo_pdf_url del módulo a ArchivoModulo y limpia legacy."""
    changed = False
    max_orden = _orden_max_archivos(modulo)
    update_fields: list[str] = []

    if modulo.video_url:
        url = modulo.video_url.strip()
        if url and not ArchivoModulo.objects.filter(
            modulo=modulo, url_externa=url, activo=True,
        ).exists():
            max_orden += 1
            ArchivoModulo.objects.bulk_create([
                ArchivoModulo(
                    modulo=modulo,
                    tipo='video',
                    titulo=f'Video — {modulo.titulo}'[:200],
                    url_externa=url,
                    orden=max_orden,
                    activo=True,
                ),
            ])
        modulo.video_url = None
        update_fields.append('video_url')
        changed = True

    if modulo.archivo_pdf_url:
        url = modulo.archivo_pdf_url.strip()
        if url and not ArchivoModulo.objects.filter(
            modulo=modulo, url_externa=url, activo=True,
        ).exists():
            max_orden += 1
            ArchivoModulo.objects.bulk_create([
                ArchivoModulo(
                    modulo=modulo,
                    tipo='pdf',
                    titulo='Documento de apoyo',
                    url_externa=url,
                    orden=max_orden,
                    activo=True,
                ),
            ])
        modulo.archivo_pdf_url = None
        update_fields.append('archivo_pdf_url')
        changed = True

    if update_fields:
        modulo.save(update_fields=update_fields)
    return changed


def archivos_leccion_profesor(modulo: Modulo) -> list[dict]:
    """Lista recursos activos con URL pública (migra legacy si aplica)."""
    migrar_recursos_legacy_modulo(modulo)
    return [
        {
            'archivo': a,
            'url': url_publica_archivo_modulo(a),
        }
        for a in ArchivoModulo.objects.filter(modulo=modulo, activo=True).order_by('orden', 'id')
    ]


def actualizar_metadatos_archivos_modulo(post, modulo: Modulo) -> None:
    archivos = list(ArchivoModulo.objects.filter(modulo=modulo, activo=True))
    for a in archivos:
        titulo = post.get(f'titulo_archivo_{a.id}', '').strip()
        if titulo:
            a.titulo = titulo[:200]
        orden_raw = post.get(f'orden_archivo_{a.id}', '').strip()
        if orden_raw.isdigit():
            a.orden = int(orden_raw)
    if archivos:
        ArchivoModulo.objects.bulk_update(archivos, ['titulo', 'orden'])


def guardar_enlaces_nuevos_modulo(post, modulo: Modulo) -> str | None:
    tipos = post.getlist('enlace_tipo_nuevo')
    urls = post.getlist('enlace_url_nuevo')
    titulos = post.getlist('enlace_titulo_nuevo')
    to_create: list[ArchivoModulo] = []
    max_orden = _orden_max_archivos(modulo)
    idx = 0
    for i, url in enumerate(urls):
        url = (url or '').strip()
        if not url:
            continue
        tipo = (tipos[i] if i < len(tipos) else '').strip()
        if tipo not in dict(ArchivoModulo.TIPOS):
            tipo = _infer_tipo_url(url)
        titulo = (titulos[i] if i < len(titulos) else '').strip() or url[:200]
        idx += 1
        to_create.append(
            ArchivoModulo(
                modulo=modulo,
                tipo=tipo,
                titulo=titulo[:200],
                url_externa=url,
                orden=max_orden + idx,
                activo=True,
            )
        )
    if to_create:
        ArchivoModulo.objects.bulk_create(to_create)
    return None


def eliminar_archivos_modulo(post, modulo: Modulo) -> None:
    ids = post.getlist('eliminar_archivo')
    if ids:
        ArchivoModulo.objects.filter(modulo=modulo, pk__in=ids).update(activo=False)


def guardar_archivos_subidos_modulo(request, modulo: Modulo) -> str | None:
    from aprende.archivos_aula import inferir_tipo_archivo_subido, validar_archivo_clase_profesor

    files = request.FILES.getlist('archivo_subir')
    if not files:
        return None
    titulo_base = request.POST.get('titulo_archivo', '').strip()
    max_orden = _orden_max_archivos(modulo)
    for i, archivo in enumerate(files):
        tipo = inferir_tipo_archivo_subido(archivo)
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
    }


def _contenido_con_bloques(contenido: str, bloques_raw: str) -> str:
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
    actualizar_metadatos_archivos_modulo(request.POST, modulo)
    eliminar_archivos_modulo(request.POST, modulo)
    err = guardar_enlaces_nuevos_modulo(request.POST, modulo)
    if err:
        return err
    return guardar_archivos_subidos_modulo(request, modulo)


def _validar_archivos_antes_crear(request) -> str | None:
    from aprende.archivos_aula import inferir_tipo_archivo_subido, validar_archivo_clase_profesor

    for archivo in request.FILES.getlist('archivo_subir'):
        try:
            validar_archivo_clase_profesor(
                archivo, tipo_hint=inferir_tipo_archivo_subido(archivo),
            )
        except ValidationError as exc:
            return exc.messages[0]
    return None


def crear_modulo_aula(request, curso: Curso) -> tuple[Modulo | None, str | None]:
    campos = _campos_leccion_desde_post(request.POST)
    bloques_raw = request.POST.get('bloques_rapidos', '')
    campos['contenido'] = _contenido_con_bloques(campos['contenido'], bloques_raw)
    try:
        validar_contenido_modulo(campos['contenido'], None)
    except ValidationError as exc:
        return None, exc.messages[0]

    err = _validar_archivos_antes_crear(request)
    if err:
        return None, err

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

    try:
        validar_contenido_modulo(modulo.contenido, modulo)
        modulo.full_clean()
    except ValidationError as exc:
        return exc.messages[0] if getattr(exc, 'messages', None) else str(exc)

    modulo.save()
    crear_secciones_desde_titulos(modulo, parse_titulos_bloques_rapidos(bloques_raw))
    return _aplicar_adjuntos_modulo(request, modulo)
