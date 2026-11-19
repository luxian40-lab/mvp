"""Congela el ensamblado vivo del curso (módulos → secciones → pasos).

No entrega WhatsApp. Solo material para CursoVersion.ensamblado.
"""
from __future__ import annotations


def congelar_ensamblado(curso) -> dict:
    """Snapshot JSON-serializable del curso tal como está en BD ahora."""
    from django.db.models import Prefetch

    from core.models import Modulo, PasoModulo, SeccionModulo

    modulos_qs = (
        Modulo.objects.filter(curso=curso)
        .order_by('numero', 'id')
        .prefetch_related(
            Prefetch(
                'secciones',
                queryset=SeccionModulo.objects.order_by('orden', 'id').prefetch_related(
                    Prefetch(
                        'pasos',
                        queryset=PasoModulo.objects.order_by('orden', 'id'),
                    ),
                ),
            ),
        )
    )
    modulos = []
    for mod in modulos_qs:
        secciones = []
        for sec in mod.secciones.all():
            pasos = []
            for paso in sec.pasos.all():
                pasos.append({
                    'id': paso.id,
                    'orden': paso.orden,
                    'tipo': paso.tipo,
                    'titulo': paso.titulo or '',
                    'contenido': paso.contenido or '',
                    'media_url': paso.media_url or '',
                    'activo': bool(paso.activo),
                })
            secciones.append({
                'id': sec.id,
                'orden': sec.orden,
                'titulo': sec.titulo or '',
                'activa': bool(sec.activa),
                'pasos': pasos,
            })
        modulos.append({
            'id': mod.id,
            'numero': mod.numero,
            'titulo': mod.titulo,
            'descripcion': mod.descripcion or '',
            'contenido': mod.contenido or '',
            'publicado_wa': bool(mod.publicado_wa),
            # Residual B4 commit 1: opcional en schema 1 (compat con snaps viejos).
            'modo_entrega': getattr(mod, 'modo_entrega', None) or 'auto',
            'secciones': secciones,
        })
    return {
        'schema': 1,
        'curso_id': curso.id,
        'curso_nombre': curso.nombre,
        'modulos': modulos,
    }
