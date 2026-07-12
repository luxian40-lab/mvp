"""Creadores Studio: publicar curso + precio COP."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import transaction

from core.models import Curso, Modulo

from .models import CreadorStudio, PublicacionStudio


def _parse_precio(raw) -> tuple[Decimal | None, str | None]:
    try:
        # Acepta "99000" o "99.000" / "99,000" (miles) → pesos enteros COP
        cleaned = str(raw).strip().replace(' ', '')
        if cleaned.count('.') == 1 and cleaned.count(',') == 0:
            # "99000.0" o similar
            precio = Decimal(cleaned).quantize(Decimal('1'))
        else:
            digits = cleaned.replace('.', '').replace(',', '')
            if not digits.isdigit():
                return None, 'Indica un precio válido en pesos (COP).'
            precio = Decimal(digits)
        if precio < 0:
            return None, 'El precio no puede ser negativo.'
        if precio > Decimal('50000000'):
            return None, 'Precio fuera de rango.'
        return precio, None
    except (InvalidOperation, ValueError, TypeError):
        return None, 'Indica un precio válido en pesos (COP).'


@transaction.atomic
def publicar_curso_creador(
    creador: CreadorStudio,
    *,
    nombre: str,
    descripcion: str,
    precio_cop,
    publicar_en_catalogo: bool = True,
) -> tuple[Curso | None, str | None]:
    nombre = (nombre or '').strip()
    descripcion = (descripcion or '').strip()
    if len(nombre) < 3:
        return None, 'El nombre del curso debe tener al menos 3 caracteres.'
    if not descripcion:
        descripcion = nombre

    precio, err = _parse_precio(precio_cop)
    if err:
        return None, err

    visible = bool(publicar_en_catalogo and creador.activo)
    curso = Curso.objects.create(
        nombre=nombre[:200],
        descripcion=descripcion,
        cliente=None,
        activo=True,
        visible_en_studio=visible,
        orden=0,
    )
    Modulo.objects.create(
        curso=curso,
        numero=1,
        titulo='Introducción',
        descripcion='Primera lección — edítala cuando prepares el contenido.',
        contenido=(
            'Bienvenido. Este es el borrador de tu primera lección.\n\n'
            'Cuando tu perfil de creador esté activo, el curso aparecerá en el catálogo de Studio '
            'y los estudiantes estudiarán en Aprende.'
        ),
    )
    PublicacionStudio.objects.create(
        curso=curso,
        creador=creador,
        precio_cop=precio,
    )
    return curso, None


@transaction.atomic
def actualizar_precio_publicacion(
    creador: CreadorStudio,
    publicacion_id: int,
    *,
    precio_cop,
    publicar_en_catalogo: bool | None = None,
) -> tuple[PublicacionStudio | None, str | None]:
    pub = PublicacionStudio.objects.filter(
        pk=publicacion_id,
        creador=creador,
    ).select_related('curso').first()
    if not pub:
        return None, 'Publicación no encontrada.'

    precio, err = _parse_precio(precio_cop)
    if err:
        return None, err

    pub.precio_cop = precio
    pub.save(update_fields=['precio_cop', 'actualizado'])

    if publicar_en_catalogo is not None:
        curso = pub.curso
        curso.visible_en_studio = bool(publicar_en_catalogo and creador.activo)
        curso.save(update_fields=['visible_en_studio'])

    return pub, None
