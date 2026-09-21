"""
Videos WhatsApp ya listos (media_wa_apto=True) no pueden quedar inactivos.

Plantilla/CE arrancan en activo=False. Si el encode deja el MP4 apto y el paso
sigue apagado, el bot no lo envía (pasos_activos_qs). Eso es el caso Innovación.
"""
from __future__ import annotations

from typing import Any

_VIDEO_EXT = ('.mp4', '.m4v', '.mov')


def es_url_video_wa(url: str) -> bool:
    low = (url or '').lower().split('?')[0]
    return any(low.endswith(ext) for ext in _VIDEO_EXT)


def qs_pasos_video_wa_listos_inactivos(modulo):
    from core.models import PasoModulo

    if not modulo or not getattr(modulo, 'pk', None):
        return PasoModulo.objects.none()
    return (
        PasoModulo.objects.filter(
            modulo=modulo,
            activo=False,
            media_wa_apto=True,
        )
        .exclude(media_url='')
        .select_related('seccion')
        .order_by('orden', 'id')
    )


def listar_pasos_video_wa_listos_inactivos(modulo) -> list:
    return [p for p in qs_pasos_video_wa_listos_inactivos(modulo) if es_url_video_wa(p.media_url)]


def contar_videos_wa_listos_inactivos(modulo) -> int:
    return len(listar_pasos_video_wa_listos_inactivos(modulo))


def mensaje_videos_wa_listos_inactivos(modulo) -> str | None:
    pasos = listar_pasos_video_wa_listos_inactivos(modulo)
    if not pasos:
        return None
    n = len(pasos)
    titulos = ', '.join(
        f'#{p.orden or p.pk} «{(p.titulo or "").strip() or "sin título"}»' for p in pasos[:4]
    )
    extra = '' if n <= 4 else f' y {n - 4} más'
    return (
        f'{n} video(s) ya listos para WhatsApp están inactivos ({titulos}{extra}). '
        'Activalos: si no, el estudiante no los recibe.'
    )


def activar_pasos_video_wa_listos(modulo) -> int:
    """Activa pasos con MP4 ya apto WA y su sección. No publica el módulo."""
    n = 0
    for paso in listar_pasos_video_wa_listos_inactivos(modulo):
        fields = []
        if not paso.activo:
            paso.activo = True
            fields.append('activo')
        if fields:
            paso.save(update_fields=fields)
        seccion = getattr(paso, 'seccion', None)
        if seccion is not None and not seccion.activa:
            seccion.activa = True
            seccion.save(update_fields=['activa'])
        n += 1
    return n


def activar_paso_por_subida_staff(paso) -> list[str]:
    """
    Staff subió o reemplazó media (no es quitar el archivo, no es CE).
    El paso y su sección quedan en la ruta de WhatsApp.
    """
    fields: list[str] = []
    if not getattr(paso, 'activo', False):
        paso.activo = True
        fields.append('activo')
    seccion = getattr(paso, 'seccion', None)
    if seccion is not None and not seccion.activa:
        seccion.activa = True
        seccion.save(update_fields=['activa'])
    return fields


def aplicar_resultado_encode_a_paso(paso, resultado: dict[str, Any]) -> list[str]:
    """Persiste URL/apto tras ffmpeg. Video apto → el paso pasa a activo."""
    url = (resultado.get('url') or '').strip()
    paso.media_url = url
    apto = resultado.get('media_wa_apto')
    paso.media_wa_apto = bool(apto) if apto is not None else None
    fields = ['media_url', 'media_wa_apto']
    if paso.media_wa_apto is True and es_url_video_wa(url):
        fields.extend(activar_paso_por_subida_staff(paso))
    paso.save(update_fields=list(dict.fromkeys(fields)))
    return fields


def reparar_curso_videos_wa_inactivos(curso, *, reset_progreso: bool = False) -> dict:
    """
    Activa MP4 ya aptos que estaban inactivos.
    Si reset_progreso=True, reinicia el índice de pasos de quienes están
    en un módulo tocado y aún no lo completaron (para que el próximo *listo*
    no se salte los videos que ahora van antes).
    """
    from core.models import ModuloCompletado, ProgresoEstudiante
    from core.module_steps import reset_progreso_pasos_modulo

    n_pasos = 0
    mods: list[int] = []
    if not curso:
        return {'pasos': 0, 'modulos': 0, 'progresos_reset': 0}
    for mod in curso.modulos.all().order_by('numero', 'id'):
        n = activar_pasos_video_wa_listos(mod)
        if n:
            n_pasos += n
            mods.append(mod.pk)
    n_prog = 0
    if reset_progreso and mods:
        for prog in ProgresoEstudiante.objects.filter(
            curso=curso, modulo_actual_id__in=mods,
        ):
            if ModuloCompletado.objects.filter(
                progreso=prog,
                modulo_id=prog.modulo_actual_id,
            ).exists():
                continue
            reset_progreso_pasos_modulo(prog)
            n_prog += 1
    return {'pasos': n_pasos, 'modulos': len(mods), 'progresos_reset': n_prog}
