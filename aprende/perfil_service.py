"""Perfil del estudiante en el aula web."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

from core.gamificacion import PerfilGamificacion
from core.gamificacion_modo import (
    gamificacion_activa,
    get_modo_gamificacion,
    modo_usa_calificacion,
    modo_usa_puntos,
    resumen_calificaciones_estudiante,
    formatear_nota,
)
from core.models import Estudiante

from .archivos_aula import validar_foto_perfil
from .models import DocumentoEstudianteAula


def resumen_perfil_aula(estudiante: Estudiante) -> dict[str, Any]:
    cliente = getattr(estudiante, 'cliente', None)
    gami_activa = gamificacion_activa(cliente)
    modo = get_modo_gamificacion(cliente) if cliente else 'puntos'

    perfil_gami = None
    puntos = None
    nivel = None
    racha = None
    promedio = None
    cantidad_notas = 0

    if gami_activa:
        perfil_gami, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
        if modo_usa_puntos(cliente):
            puntos = perfil_gami.puntos_totales
            nivel = perfil_gami.nivel
            racha = perfil_gami.racha_dias_actual
        elif modo_usa_calificacion(cliente):
            resumen = resumen_calificaciones_estudiante(estudiante)
            promedio = resumen.get('promedio')
            cantidad_notas = resumen.get('cantidad') or 0
            if promedio is not None:
                promedio = formatear_nota(promedio)

    documentos = (
        DocumentoEstudianteAula.objects.filter(estudiante=estudiante)
        .select_related('curso', 'modulo')
        .order_by('-fecha_subida')[:50]
    )

    return {
        'gamificacion_activa': gami_activa,
        'modo_gamificacion': modo,
        'perfil_gamificacion': perfil_gami,
        'puntos': puntos,
        'nivel': nivel,
        'racha': racha,
        'promedio': promedio,
        'cantidad_notas': cantidad_notas,
        'documentos': documentos,
    }


def actualizar_perfil_aula(request, estudiante: Estudiante) -> str | None:
    nombre = request.POST.get('nombre', '').strip()
    if not nombre:
        return 'El nombre es obligatorio.'
    if len(nombre) > 100:
        return 'El nombre es demasiado largo.'

    estudiante.nombre = nombre
    estudiante.municipio = request.POST.get('municipio', '').strip()[:100]
    estudiante.departamento = request.POST.get('departamento', '').strip()[:100]
    estudiante.ubicacion_detalle = request.POST.get('ubicacion_detalle', '').strip()
    genero = request.POST.get('genero', '').strip()
    if genero in dict(Estudiante.GENERO_CHOICES):
        estudiante.genero = genero

    raw_edad = request.POST.get('edad', '').strip()
    if raw_edad:
        try:
            edad = int(raw_edad)
        except ValueError:
            return 'La edad debe ser un número.'
        if not 5 <= edad <= 120:
            return 'Indica una edad válida (5–120 años).'
        estudiante.edad = edad
    else:
        estudiante.edad = None

    foto = request.FILES.get('foto_perfil')
    if foto:
        try:
            validar_foto_perfil(foto)
        except ValidationError as exc:
            return exc.messages[0]
        if estudiante.foto_perfil:
            estudiante.foto_perfil.delete(save=False)
        estudiante.foto_perfil = foto

    estudiante.save()
    return None
