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
            from django.conf import settings as dj_settings

            msg = (
                f'Video paso {paso.orden or paso.pk}: aptitud WA sin verificar (recomendado auditar).'
            )
            if getattr(dj_settings, 'PUBLICAR_MODULO_REQUIRE_MEDIA_QA', False):
                errores.append(
                    f'Video paso {paso.orden or paso.pk}: no publicar hasta QA media '
                    '(media_wa_apto vacío).'
                )
            else:
                avisos.append(msg)

    return ChecklistPublicacion(ok=not errores, errores=errores, avisos=avisos)


def publicar_modulo_wa(
    modulo: Modulo,
    *,
    usuario=None,
    registrar_evento: bool = True,
) -> tuple[bool, list[str]]:
    snapshot_antes = snapshot_modulo_publicacion(modulo) if registrar_evento else {}
    from django.conf import settings as dj_settings

    head = bool(getattr(dj_settings, 'PUBLICAR_MODULO_HEAD_QA', False))
    qa = validar_modulo_qa(modulo, head_urls=head)
    if not qa.ok:
        return False, qa.errores
    if modulo.publicado_wa:
        return True, []
    modulo.publicado_wa = True
    modulo.save(update_fields=['publicado_wa'])
    if registrar_evento:
        snapshot_despues = snapshot_modulo_publicacion(modulo)
        diff = diff_snapshots(snapshot_antes, snapshot_despues)
        _registrar_evento_publicacion(
            modulo,
            usuario=usuario,
            accion='publicar',
            snapshot_antes=snapshot_antes,
            snapshot_despues=snapshot_despues,
            diff_resumen=diff,
        )
    return True, []


def estado_media_paso(paso) -> tuple[str, str]:
    """
    Semáforo pre-63019 para un paso.
    Returns (codigo, etiqueta): ok | warn | fail | na
    """
    url = (getattr(paso, 'media_url', None) or '').strip()
    if not url:
        return 'na', '—'
    if paso and getattr(paso, 'pk', None):
        from core.media_encode_async import estado_encode_paso

        enc = estado_encode_paso(paso.pk)
        if enc:
            st = enc.get('status')
            if st in ('pending', 'running'):
                return 'warn', '🟡 Procesando video…'
            if st == 'error':
                err = (enc.get('error') or 'encode falló')[:48]
                return 'fail', f'🔴 {err}'
    low = url.lower().split('?')[0]
    if not low.endswith(('.mp4', '.m4v', '.mov', '.mp3', '.m4a', '.ogg', '.wav', '.jpg', '.jpeg', '.png', '.webp', '.pdf')):
        return 'na', 'Sin media WA'
    apto = getattr(paso, 'media_wa_apto', None)
    if apto is False:
        return 'fail', '🔴 No apto WA'
    if apto is True:
        return 'ok', '🟢 Apto WA'
    if low.endswith(('.mp4', '.m4v', '.mov')):
        return 'warn', '🟡 Sin verificar'
    return 'ok', '🟢 URL media'


def _head_url_ok(url: str, timeout: float = 4.0) -> bool | None:
    """True=OK, False=404/error, None=skip (local sin red)."""
    if not url or url.startswith('/'):
        return None
    try:
        import urllib.request

        req = urllib.request.Request(
            url,
            method='HEAD',
            headers={'User-Agent': 'eki-qa-publicacion/1.0'},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


def validar_modulo_qa(
    modulo: Modulo | None,
    *,
    head_urls: bool = False,
) -> ChecklistPublicacion:
    """Checklist + opcional HEAD S3/URL antes de publicar."""
    base = evaluar_checklist_publicacion_detalle(modulo)
    if modulo is None or not head_urls:
        return base
    from .module_steps import pasos_activos_qs

    for paso in pasos_activos_qs(modulo):
        url = (paso.media_url or '').strip()
        if not url:
            continue
        low = url.lower().split('?')[0]
        if not low.endswith(('.mp4', '.m4v', '.mov', '.mp3', '.m4a', '.jpg', '.jpeg', '.png', '.pdf')):
            continue
        head = _head_url_ok(url)
        if head is False:
            base.errores.append(
                f'Media paso {paso.orden or paso.pk}: URL no responde (HEAD).'
            )
        elif head is None:
            base.avisos.append(
                f'Media paso {paso.orden or paso.pk}: HEAD omitido (URL relativa/local).'
            )
    base.ok = not base.errores
    return base


def snapshot_modulo_publicacion(modulo: Modulo | None) -> dict:
    if modulo is None:
        return {}
    from .module_steps import pasos_activos_qs

    pasos = []
    for p in pasos_activos_qs(modulo).order_by('orden', 'id'):
        pasos.append(
            {
                'id': p.pk,
                'orden': p.orden,
                'titulo': (p.titulo or '')[:120],
                'media_url': (p.media_url or '')[:200],
                'media_wa_apto': p.media_wa_apto,
                'activo': p.activo,
            }
        )
    return {
        'modulo_id': modulo.pk,
        'numero': modulo.numero,
        'titulo': modulo.titulo,
        'publicado_wa': bool(modulo.publicado_wa),
        'n_pasos_activos': len(pasos),
        'pasos': pasos,
    }


def diff_snapshots(antes: dict, despues: dict) -> list[str]:
    if not antes:
        return ['Primera publicación del módulo.']
    cambios: list[str] = []
    if antes.get('publicado_wa') != despues.get('publicado_wa'):
        cambios.append(
            'Estado WA: '
            f"{'publicado' if despues.get('publicado_wa') else 'borrador'}"
        )
    n_antes = antes.get('n_pasos_activos', 0)
    n_des = despues.get('n_pasos_activos', 0)
    if n_antes != n_des:
        cambios.append(f'Pasos activos: {n_antes} → {n_des}')
    ids_antes = {p['id']: p for p in antes.get('pasos', [])}
    ids_des = {p['id']: p for p in despues.get('pasos', [])}
    for pid, p in ids_des.items():
        prev = ids_antes.get(pid)
        if not prev:
            cambios.append(f'+ Paso {p.get("orden")}: {(p.get("titulo") or "")[:40]}')
            continue
        if prev.get('media_url') != p.get('media_url'):
            cambios.append(f'~ Media paso {p.get("orden")} actualizada')
        if prev.get('media_wa_apto') != p.get('media_wa_apto'):
            cambios.append(
                f'~ Apto WA paso {p.get("orden")}: '
                f'{prev.get("media_wa_apto")} → {p.get("media_wa_apto")}'
            )
    for pid, p in ids_antes.items():
        if pid not in ids_des:
            cambios.append(f'- Paso {p.get("orden")} removido/inactivo')
    if not cambios:
        cambios.append('Sin cambios detectados en snapshot (re-publicación).')
    return cambios[:20]


def _registrar_evento_publicacion(
    modulo: Modulo,
    *,
    usuario,
    accion: str,
    snapshot_antes: dict,
    snapshot_despues: dict,
    diff_resumen: list[str],
) -> None:
    from .models import ModuloPublicacionEvent

    ModuloPublicacionEvent.objects.create(
        modulo=modulo,
        usuario=usuario,
        accion=accion,
        snapshot_antes=snapshot_antes,
        snapshot_despues=snapshot_despues,
        diff_resumen=diff_resumen,
    )


def publicar_modulos_bulk(
    curso: Curso | None,
    modulos_ids: list[int] | None = None,
    *,
    usuario=None,
) -> tuple[int, list[str]]:
    """Publica módulos que pasen checklist. Returns (publicados, errores)."""
    if curso is None:
        return 0, ['Curso inválido.']
    qs = curso.modulos.filter(publicado_wa=False).order_by('numero', 'id')
    if modulos_ids:
        qs = qs.filter(pk__in=modulos_ids)
    publicados = 0
    errores: list[str] = []
    for mod in qs:
        ok, errs = publicar_modulo_wa(mod, usuario=usuario)
        if ok:
            publicados += 1
        else:
            errores.append(f'M{mod.numero}: {errs[0] if errs else "error"}')
    return publicados, errores


def cursos_listos_para_campana_ids() -> list[int]:
    """IDs de cursos WA con M1 publicado y checklist OK."""
    from .models import Curso

    ids = []
    for curso in Curso.objects.filter(activo=True).exclude(modo_aula=Curso.MODO_AULA_CLASES):
        ok, _ = curso_listo_para_campana_wa(curso)
        if ok:
            ids.append(curso.pk)
    return ids


def campanas_programadas_con_borradores() -> list[dict]:
    """Campañas futuras cuyo curso destino tiene módulos borrador."""
    from django.utils import timezone

    from .models import Campana, Modulo

    ahora = timezone.now()
    out = []
    qs = (
        Campana.objects.filter(
            ejecutada=False,
            fecha_programada__gte=ahora,
            es_campana_curso=True,
            curso_destino__isnull=False,
        )
        .select_related('curso_destino', 'cliente')
        .order_by('fecha_programada')[:20]
    )
    for camp in qs:
        curso = camp.curso_destino
        if curso is None or curso.es_modo_clases():
            continue
        n_borr = Modulo.objects.filter(curso=curso, publicado_wa=False).count()
        if n_borr < 1:
            continue
        out.append(
            {
                'campana_id': camp.pk,
                'campana_nombre': camp.nombre,
                'curso_id': curso.pk,
                'curso_nombre': curso.nombre,
                'fecha_programada': camp.fecha_programada,
                'n_borradores': n_borr,
            }
        )
    return out


def notificar_borrador_curso_activo(modulo: Modulo) -> None:
    """Slack si curso con inscritos recibe módulo borrador nuevo."""
    from django.core.cache import cache

    from .models import ProgresoEstudiante
    from .ops_slack import notify_slack_ops

    curso = getattr(modulo, 'curso', None)
    if curso is None or modulo.publicado_wa or curso.es_modo_clases():
        return
    inscritos = ProgresoEstudiante.objects.filter(curso=curso).count()
    if inscritos < 1:
        return
    key = f'eki_slack_borrador_curso_{curso.pk}'
    if cache.get(key):
        return
    cache.set(key, 1, timeout=6 * 3600)
    notify_slack_ops(
        f'Curso *{curso.nombre}* ({inscritos} inscrito(s)): '
        f'nuevo módulo M{modulo.numero} en *borrador* WA.\n'
        f'Admin: /admin/core/curso/{curso.pk}/change/',
        title='eki · módulo borrador en curso activo',
    )


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
