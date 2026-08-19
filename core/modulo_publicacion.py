"""
Publicación de módulos para WhatsApp: borrador vs listo para campo.

Cursos modo clases (Aprende) no usan el gate WA — Capital Humano y similares.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Curso, Estudiante, Modulo, ProgresoEstudiante


def curso_usa_gate_publicacion_wa(curso: Curso | None) -> bool:
    if curso is None:
        return False
    return not curso.es_modo_clases()


def modulos_publicados_wa_qs(curso: Curso | None):
    from .models import Modulo

    if curso is None:
        return Modulo.objects.none()
    if not curso_usa_gate_publicacion_wa(curso):
        return curso.modulos.all()
    return curso.modulos.filter(publicado_wa=True)


def modulos_publicados_wa(curso: Curso | None) -> list:
    return list(modulos_publicados_wa_qs(curso).order_by('numero', 'id'))


def total_modulos_publicados_wa(curso: Curso | None) -> int:
    return modulos_publicados_wa_qs(curso).count()


def primer_modulo_curso(curso: Curso | None):
    if curso is None:
        return None
    return curso.modulos.order_by('numero', 'id').first()


def primer_modulo_publicado_wa(curso: Curso | None):
    return modulos_publicados_wa_qs(curso).order_by('numero', 'id').first()


def siguiente_modulo_publicado_wa(curso: Curso | None, modulo_actual) -> Modulo | None:
    """
    Siguiente módulo en orden estricto (M+1). No salta borradores hacia M+2.
    None = fin de curso o el siguiente slot aún no está publicado.
    """
    if curso is None:
        return None
    if modulo_actual is None:
        primero = curso.modulos.order_by('numero', 'id').first()
        if primero is None:
            return None
        if curso_usa_gate_publicacion_wa(curso) and not primero.publicado_wa:
            return None
        return primero
    try:
        num = int(modulo_actual.numero)
    except (TypeError, ValueError, AttributeError):
        return None
    siguiente = curso.modulos.filter(numero__gt=num).order_by('numero', 'id').first()
    if siguiente is None:
        return None
    if curso_usa_gate_publicacion_wa(curso) and not siguiente.publicado_wa:
        return None
    return siguiente


def hay_modulos_despues(curso: Curso | None, modulo_actual) -> bool:
    if curso is None or modulo_actual is None:
        return False
    try:
        num = int(modulo_actual.numero)
    except (TypeError, ValueError, AttributeError):
        return False
    return curso.modulos.filter(numero__gt=num).exists()


def hay_modulos_no_publicados_despues(curso: Curso | None, modulo_actual) -> bool:
    if not curso_usa_gate_publicacion_wa(curso) or modulo_actual is None:
        return False
    try:
        num = int(modulo_actual.numero)
    except (TypeError, ValueError, AttributeError):
        return False
    return curso.modulos.filter(numero__gt=num, publicado_wa=False).exists()


def numeros_cierre_curso_publicados(curso: Curso | None) -> tuple[int | None, int | None]:
    """Penúltimo y último número entre módulos publicados WA (o todos si modo clases)."""
    nums = list(
        modulos_publicados_wa_qs(curso).order_by('numero', 'id').values_list('numero', flat=True)
    )
    if not nums:
        return None, None
    ultimo = nums[-1]
    penultimo = nums[-2] if len(nums) >= 2 else None
    return penultimo, ultimo


def format_mensaje_bloqueo_contenido_pendiente(cliente=None) -> str:
    """Mismo tono que drip; el estudiante no distingue causa."""
    from .avance_whatsapp import texto_bloqueo_drip_cierre

    return (
        '🌱 *¡Excelente energía!*\n\n'
        'Estamos preparando tu siguiente sesión; aún no enviamos el siguiente módulo '
        'para que puedas asimilar lo aprendido.\n\n'
        'Tu próxima lección estará disponible pronto.\n'
        'Mientras tanto, repasa el material del módulo que acabas de completar.\n\n'
        f'{texto_bloqueo_drip_cierre(cliente)}'
    )


def mensaje_bloqueo_sin_siguiente_publicado(
    estudiante: Estudiante | None,
    progreso: ProgresoEstudiante | None,
    modulo_actual,
) -> str | None:
    """
    None = puede intentar avanzar (hay siguiente publicado o fin real del curso).
    Mensaje = bloqueo amable (siguiente módulo aún en borrador).
    """
    if progreso is None:
        return None
    curso = progreso.curso
    if not curso_usa_gate_publicacion_wa(curso):
        return None
    if siguiente_modulo_publicado_wa(curso, modulo_actual):
        return None
    if not hay_modulos_despues(curso, modulo_actual):
        return None
    cliente = getattr(estudiante, 'cliente', None) if estudiante else None
    return format_mensaje_bloqueo_contenido_pendiente(cliente)


def curso_listo_para_campana_wa(curso: Curso | None) -> tuple[bool, str]:
    """Primer módulo del curso debe estar publicado para WA."""
    if curso is None or not curso_usa_gate_publicacion_wa(curso):
        return True, ''
    primero = primer_modulo_curso(curso)
    if primero is None:
        return False, 'El curso no tiene módulos.'
    if not primero.publicado_wa:
        return False, (
            f'Publicá el Módulo {primero.numero} («{primero.titulo}») antes de lanzar '
            'campaña o inscripción masiva por WhatsApp.'
        )
    ok, errores = evaluar_checklist_publicacion(primero)
    if not ok:
        return False, errores[0] if errores else 'Módulo 1 no cumple checklist de publicación.'
    return True, ''


@dataclass
class ChecklistPublicacion:
    ok: bool
    errores: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _modulo_tiene_material_minimo(modulo: Modulo) -> bool:
    from .module_steps import pasos_activos_qs

    if pasos_activos_qs(modulo).exists():
        return True
    if (modulo.contenido or '').strip():
        return True
    if (modulo.video_url or '').strip() or modulo.video_archivo:
        return True
    if modulo.archivos_multimedia.filter(activo=True).exists():
        return True
    return False


def evaluar_checklist_publicacion(modulo: Modulo | None) -> tuple[bool, list[str]]:
    result = evaluar_checklist_publicacion_detalle(modulo)
    return result.ok, result.errores


def evaluar_checklist_publicacion_detalle(modulo: Modulo | None) -> ChecklistPublicacion:
    if modulo is None:
        return ChecklistPublicacion(ok=False, errores=['Módulo inexistente.'])

    errores: list[str] = []
    avisos: list[str] = []

    if not _modulo_tiene_material_minimo(modulo):
        errores.append(
            'Falta contenido: agregá pasos activos, texto legacy, video o archivos multimedia.'
        )

    from .module_structure import modulo_tiene_secciones_intercaladas, mensaje_error_intercalado

    hall = modulo_tiene_secciones_intercaladas(modulo)
    if hall:
        errores.append(mensaje_error_intercalado(hall))

    from .module_steps import pasos_activos_qs

    for paso in pasos_activos_qs(modulo):
        url = (paso.media_url or '').strip()
        if not url:
            continue
        low = url.lower().split('?')[0]
        if not low.endswith(('.mp4', '.m4v', '.mov', '.mp3', '.m4a', '.ogg', '.wav')):
            continue
        if paso.media_wa_apto is False:
            errores.append(
                f'Video/audio del paso {paso.orden or paso.pk} no es apto para WhatsApp '
                '(revisá codec o subí versión wa_safe).'
            )
        elif paso.media_wa_apto is None and low.endswith(('.mp4', '.m4v', '.mov')):
            avisos.append(
                f'Video paso {paso.orden or paso.pk}: aptitud WA sin verificar (recomendado auditar).'
            )

    return ChecklistPublicacion(ok=not errores, errores=errores, avisos=avisos)


def publicar_modulo_wa(modulo: Modulo) -> tuple[bool, list[str]]:
    ok, errores = evaluar_checklist_publicacion(modulo)
    if not ok:
        return False, errores
    if modulo.publicado_wa:
        return True, []
    modulo.publicado_wa = True
    modulo.save(update_fields=['publicado_wa'])
    return True, []


def resumen_publicacion_curso(curso: Curso | None) -> dict:
    """Datos para semáforos en ficha curso (admin)."""
    if curso is None:
        return {}
    mods = list(curso.modulos.order_by('numero', 'id'))
    publicados = sum(1 for m in mods if m.publicado_wa)
    borradores = len(mods) - publicados
    filas = []
    for m in mods:
        chk = evaluar_checklist_publicacion_detalle(m)
        filas.append(
            {
                'modulo': m,
                'publicado': bool(m.publicado_wa),
                'checklist_ok': chk.ok,
                'errores': chk.errores,
                'avisos': chk.avisos,
            }
        )
    listo_campana, msg_campana = curso_listo_para_campana_wa(curso)
    return {
        'usa_wa': curso_usa_gate_publicacion_wa(curso),
        'total': len(mods),
        'publicados': publicados,
        'borradores': borradores,
        'filas': filas,
        'listo_campana': listo_campana,
        'msg_campana': msg_campana,
    }
