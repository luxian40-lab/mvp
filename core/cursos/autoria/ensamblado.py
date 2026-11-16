"""Congela el ensamblado vivo del curso (módulos → secciones → pasos).

No entrega WhatsApp. Solo material para CursoVersion.ensamblado.
"""
from __future__ import annotations


def congelar_ensamblado(curso) -> dict:
    """Snapshot JSON-serializable del curso tal como está en BD ahora."""
    from core.models import Modulo, PasoModulo, SeccionModulo

    modulos = []
    for mod in Modulo.objects.filter(curso=curso).order_by('numero', 'id'):
        secciones = []
        for sec in SeccionModulo.objects.filter(modulo=mod).order_by('orden', 'id'):
            pasos = []
            for paso in PasoModulo.objects.filter(seccion=sec).order_by('orden', 'id'):
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
            'secciones': secciones,
        })
    return {
        'schema': 1,
        'curso_id': curso.id,
        'curso_nombre': curso.nombre,
        'modulos': modulos,
    }
