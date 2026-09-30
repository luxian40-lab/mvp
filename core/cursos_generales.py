# -*- coding: utf-8 -*-
"""Cursos sin cliente: los ve cualquier estudiante. El menú solo muestra catalogo_menu."""
from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import Count

logger = logging.getLogger(__name__)

NOMBRE_RIENDAS = 'Tome las riendas de su dinero'
NOMBRE_INNOVACION = 'Innovación e IA para nuevos emprendedores'
NOMBRE_TIEMPO = 'Gestión de tiempo y productividad personal en el campo'

URL_RIENDAS = 'https://www.eki.com.co/programas#tome-las-riendas-de-su-dinero'
URL_INNOVACION = 'https://www.eki.com.co/programas#innovacion-e-ia-para-nuevos-emprendedores'
URL_TIEMPO = 'https://www.eki.com.co/programas#gestion-de-tiempo-y-productividad-personal-en-el-campo'

CATALOGO = (
    {
        'clave': 'riendas',
        'nombre': NOMBRE_RIENDAS,
        'buscar': 'riendas de su dinero',
        'resumen': 'La plata de la semana: anotar, ver a dónde se va y decidir.',
        'url': URL_RIENDAS,
        'emoji': '📒',
        'imagen': 'carrusel_riendas.jpg',
        'origen': True,
    },
    {
        'clave': 'innovacion',
        'nombre': NOMBRE_INNOVACION,
        'buscar': 'Innovación e IA para nuevos emprendedores',
        'resumen': 'Innovar con propósito y usar la inteligencia artificial en el negocio.',
        'url': URL_INNOVACION,
        'emoji': '✨',
        'imagen': 'carrusel_innovacion.jpg',
        'origen': True,
    },
    {
        'clave': 'tiempo',
        'nombre': NOMBRE_TIEMPO,
        'buscar': '',
        'resumen': 'Prioridades, jornada y hábitos para el trabajo en el campo.',
        'url': URL_TIEMPO,
        'emoji': '⏱️',
        'imagen': 'carrusel_tiempo.jpg',
        'origen': False,
    },
)

_PAYLOADS = {}
for _item in CATALOGO:
    _PAYLOADS[f"ver_{_item['clave']}"] = ('ver', _item['clave'])
    _PAYLOADS[f"info_{_item['clave']}"] = ('info', _item['clave'])


def payload_catalogo(body: str) -> dict | None:
    par = _PAYLOADS.get((body or '').strip().lower())
    if not par:
        return None
    return {'accion': par[0], 'clave': par[1]}


def texto_tarjeta(item: dict) -> str:
    """Cuerpo de la card. WhatsApp admite 160 caracteres y dos saltos de línea."""
    nombre = f"*{item['nombre']}*"
    resumen = (item.get('resumen') or '').strip()
    texto = f"{nombre}\n{resumen}" if resumen else nombre
    return texto[:160]


def url_imagen_catalogo(archivo: str) -> str:
    from django.conf import settings
    from django.contrib.staticfiles.storage import staticfiles_storage

    path = staticfiles_storage.url(f'carrusel/{archivo}')
    if path.startswith('http'):
        return path
    base = (getattr(settings, 'ADMIN_PUBLIC_URL', '') or 'https://admin.eki.technology').rstrip('/')
    if not path.startswith('/'):
        path = '/' + path
    return f'{base}{path}'


def tarjetas_catalogo() -> list[dict]:
    tarjetas = []
    for item in CATALOGO:
        tarjetas.append({
            'clave': item['clave'],
            'body': texto_tarjeta(item),
            'imagen': url_imagen_catalogo(item['imagen']),
            'url': item['url'],
            'botones': [
                (f"ver_{item['clave']}", 'Ver curso'),
                (f"info_{item['clave']}", 'Más información'),
            ],
        })
    return tarjetas


def item_catalogo(clave: str) -> dict | None:
    for item in CATALOGO:
        if item['clave'] == clave:
            return item
    return None


def curso_catalogo(clave: str):
    from core.models import Curso

    item = item_catalogo(clave)
    if item is None:
        return None
    return (
        Curso.objects.filter(nombre=item['nombre'], cliente__isnull=True, catalogo_menu=True, activo=True)
        .order_by('id')
        .first()
    )


def asegurar_cursos_generales() -> dict:
    """Copia Riendas e Innovación si hay origen. Crea el curso de tiempo (5 módulos). Idempotente."""
    salida = {}
    for item in CATALOGO:
        if item['origen']:
            salida[item['clave']] = _asegurar_copia(item)
        else:
            salida[item['clave']] = _asegurar_tiempo(item)
    return salida


def _curso_destino(item: dict):
    from core.models import Curso

    curso = Curso.objects.filter(nombre=item['nombre'], cliente__isnull=True).order_by('id').first()
    if curso is None:
        curso = Curso.objects.create(
            nombre=item['nombre'],
            descripcion=item['resumen'],
            emoji=(item.get('emoji') or '')[:10],
            cliente=None,
            activo=True,
            catalogo_menu=True,
            usar_agentes_ia=False,
            dias_espera_entre_modulos=0,
            duracion_semanas=5,
        )
        return curso, True
    dirty = []
    if not curso.catalogo_menu:
        curso.catalogo_menu = True
        dirty.append('catalogo_menu')
    if not curso.activo:
        curso.activo = True
        dirty.append('activo')
    if dirty:
        curso.save(update_fields=dirty)
    return curso, False


def _buscar_origen(item: dict, destino_id: int):
    from core.models import Curso

    qs = (
        Curso.objects.filter(activo=True, nombre__icontains=item['buscar'])
        .exclude(pk=destino_id)
        .exclude(catalogo_menu=True)
        .annotate(n_mod=Count('modulos'))
        .filter(n_mod__gt=0)
    )
    con_cliente = qs.filter(cliente__isnull=False).order_by('-n_mod', 'id').first()
    if con_cliente is not None:
        return con_cliente
    return qs.order_by('-n_mod', 'id').first()


def _asegurar_copia(item: dict) -> dict:
    destino, creado = _curso_destino(item)
    if destino.modulos.exists():
        return {
            'ok': True,
            'destino_id': destino.id,
            'creado': creado,
            'copiado': False,
            'ya_tenia_modulos': True,
        }
    origen = _buscar_origen(item, destino.id)
    if origen is None:
        return {
            'ok': False,
            'error': 'sin_origen',
            'destino_id': destino.id,
            'creado': creado,
        }
    copiados = _clonar_contenido(origen, destino)
    return {
        'ok': True,
        'destino_id': destino.id,
        'origen_id': origen.id,
        'creado': creado,
        'copiado': True,
        **copiados,
    }


def _asegurar_tiempo(item: dict) -> dict:
    destino, creado = _curso_destino(item)
    if destino.modulos.exists():
        return {'ok': True, 'destino_id': destino.id, 'creado': creado, 'modulos': destino.modulos.count()}
    _crear_modulos_tiempo(destino)
    return {'ok': True, 'destino_id': destino.id, 'creado': creado, 'modulos': 5}


@transaction.atomic
def _clonar_contenido(origen, destino) -> dict:
    from core.models import Modulo, PasoModulo, SeccionModulo
    from core.models_extras import ArchivoModulo

    modulos = 0
    pasos = 0
    archivos = 0
    for mod_o in Modulo.objects.filter(curso=origen).order_by('numero', 'id'):
        mod_d = Modulo.objects.create(
            curso=destino,
            numero=mod_o.numero,
            titulo=mod_o.titulo,
            descripcion=mod_o.descripcion or mod_o.titulo,
            contenido=mod_o.contenido or '',
            modo_entrega=mod_o.modo_entrega,
            video_url=mod_o.video_url,
            imagen_portada_url=mod_o.imagen_portada_url,
            publicado_wa=True,
            duracion_dias=mod_o.duracion_dias,
            secciones_por_listo=mod_o.secciones_por_listo or 1,
        )
        if getattr(mod_o, 'archivo_pdf_url', None):
            mod_d.archivo_pdf_url = mod_o.archivo_pdf_url
            mod_d.save(update_fields=['archivo_pdf_url'])
        modulos += 1
        seccion_map = {}
        for sec in SeccionModulo.objects.filter(modulo=mod_o).order_by('orden', 'id'):
            nueva = SeccionModulo.objects.create(
                modulo=mod_d,
                orden=sec.orden,
                titulo=sec.titulo or '',
                activa=sec.activa,
            )
            seccion_map[sec.id] = nueva
        for paso in PasoModulo.objects.filter(modulo=mod_o).order_by('orden', 'id'):
            sec_nueva = seccion_map.get(paso.seccion_id)
            if sec_nueva is None:
                continue
            PasoModulo.objects.create(
                modulo=mod_d,
                seccion=sec_nueva,
                orden=paso.orden,
                titulo=paso.titulo or '',
                tipo=paso.tipo,
                contenido=paso.contenido or '',
                media_url=paso.media_url or '',
                video_entrega=getattr(paso, 'video_entrega', None) or PasoModulo.VIDEO_WHATSAPP,
                media_wa_apto=paso.media_wa_apto,
                eval_opcion_a=paso.eval_opcion_a or '',
                eval_opcion_b=paso.eval_opcion_b or '',
                eval_opcion_c=paso.eval_opcion_c or '',
                eval_opcion_d=paso.eval_opcion_d or '',
                opciones_json=paso.opciones_json,
                respuesta_correcta=paso.respuesta_correcta or '',
                feedback_correcto=paso.feedback_correcto or '',
                feedback_incorrecto=paso.feedback_incorrecto or '',
                activo=paso.activo,
                requiere_listo_para_avanzar=paso.requiere_listo_para_avanzar,
            )
            pasos += 1
        for archivo in ArchivoModulo.objects.filter(modulo=mod_o, activo=True).order_by('orden', 'id'):
            nuevo = ArchivoModulo(
                modulo=mod_d,
                tipo=archivo.tipo,
                titulo=archivo.titulo,
                descripcion=archivo.descripcion or '',
                url_externa=archivo.url_externa or '',
                disponible_offline=archivo.disponible_offline,
                orden=archivo.orden,
                activo=True,
                tamano_bytes=archivo.tamano_bytes,
                duracion_segundos=archivo.duracion_segundos,
            )
            if archivo.archivo:
                nuevo.archivo = archivo.archivo
            try:
                ArchivoModulo.objects.bulk_create([nuevo])
                archivos += 1
            except Exception:
                logger.exception('clon_archivo_general_fail origen=%s', archivo.id)
    return {'modulos': modulos, 'pasos': pasos, 'archivos': archivos}


def _crear_modulos_tiempo(curso) -> None:
    from core.models import Modulo

    aviso = (
        'Los videos y podcasts de este programa están en la ficha de eki.com.co/programas. '
        'Aquí va el texto de cada tema; no hay archivo de video adjunto.'
    )
    modulos = (
        (
            1,
            'Bienvenida e importancia del tiempo',
            'Qué ocupa el día y qué merece la atención.',
            '¡Bienvenido al curso Gestión del tiempo y productividad personal en el campo! '
            'Sabemos que cada jornada trae múltiples responsabilidades y que muchas veces el día parece no alcanzar. '
            'Durante cinco módulos usted aprenderá a definir prioridades, organizar mejor sus tareas, reducir distracciones, '
            'aprovechar sus recursos y construir hábitos que le ayuden a avanzar hacia sus metas sin descuidar su bienestar.\n\n'
            '¿Siente que trabaja todo el día y, aun así, quedan cosas importantes por hacer? '
            'En este módulo usted identificará qué actividades están consumiendo su tiempo y cuáles merecen realmente su atención. '
            'El tiempo es un recurso que debe administrar: reconozca sus principales desafíos y convierta sus propósitos en metas claras.\n\n'
            + aviso,
        ),
        (
            2,
            'Herramientas y técnicas',
            'Plan de la jornada, listas y cuándo delegar.',
            'Tener claras sus prioridades es importante, pero ahora viene el siguiente paso: convertirlas en un plan. '
            'En este módulo usted aprenderá métodos sencillos para organizar su jornada, hacer listas de tareas, '
            'distribuir mejor su tiempo y aprovechar los recursos que tiene a su alcance. '
            'También descubrirá que ser productivo no significa hacerlo todo solo, sino saber cuándo y cómo delegar.\n\n'
            'Al finalizar, usted tendrá herramientas prácticas para organizar mejor su trabajo y tomar decisiones '
            'sobre qué hacer, cuándo hacerlo y quién puede apoyarlo.\n\n'
            + aviso,
        ),
        (
            3,
            'Productividad y ladrones de tiempo',
            'Distracciones, concentración y equilibrio.',
            'Ahora que usted ya sabe planificar mejor su jornada, es momento de cuidar su atención y su energía. '
            'En este módulo aprenderá a reconocer las distracciones que afectan su productividad, aplicar técnicas sencillas '
            'para concentrarse mejor y manejar el estrés de forma más saludable. '
            'También reflexionará sobre cómo encontrar un mejor equilibrio entre el trabajo, el descanso y su vida personal.\n\n'
            'La productividad no consiste en hacer más cosas, sino en aprovechar mejor su tiempo sin desgastarse en el proceso.\n\n'
            + aviso,
        ),
        (
            4,
            'Organización del espacio',
            'Herramientas, bodega y tecnología a favor.',
            'El lugar donde usted trabaja también influye en la forma en que aprovecha su tiempo. '
            'En este módulo aprenderá a organizar mejor sus herramientas, materiales y espacios para evitar pérdidas innecesarias '
            'y facilitar sus actividades diarias. Además, conocerá formas sencillas de usar la tecnología para guardar, '
            'consultar y organizar información importante de su trabajo.\n\n'
            'Un entorno más ordenado puede ayudarle a trabajar con mayor agilidad y tener más claridad sobre lo que necesita.\n\n'
            + aviso,
        ),
        (
            5,
            'Hábitos y disciplina',
            'Rutinas, constancia y no dejarlo para mañana.',
            'Organizarse mejor por unos días es útil, pero el verdadero cambio aparece cuando esas acciones se convierten en hábitos. '
            'En este último módulo usted aprenderá a crear rutinas que pueda mantener, fortalecer su disciplina y reconocer '
            'por qué a veces dejamos para después tareas importantes. También encontrará estrategias para sostener su motivación '
            'y avanzar con constancia hacia sus metas.\n\n'
            'Llegamos al final del curso, pero el verdadero cambio comienza ahora. Cada decisión sobre cómo usar su tiempo '
            'puede acercarlo a una vida más organizada y con propósito. Empiece con un pequeño cambio, manténgalo en el tiempo '
            'y recuerde: administrar mejor su tiempo es también cuidar lo que más valora en su vida.\n\n'
            + aviso,
        ),
    )
    with transaction.atomic():
        for numero, titulo, descripcion, contenido in modulos:
            Modulo.objects.create(
                curso=curso,
                numero=numero,
                titulo=titulo,
                descripcion=descripcion,
                contenido=contenido,
                modo_entrega=Modulo.MODO_ENTREGA_LEGACY,
                publicado_wa=True,
                duracion_dias=7,
            )


def cupo_catalogo_del_mes(estudiante, curso):
    """Otro curso general ya empezado en el mes calendario (America/Bogota)."""
    from django.utils import timezone

    from core.models import ProgresoEstudiante

    ahora = timezone.localtime()
    inicio_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (
        ProgresoEstudiante.objects.filter(
            estudiante=estudiante,
            curso__catalogo_menu=True,
            fecha_inicio__gte=inicio_mes,
        )
        .exclude(curso_id=curso.id)
        .select_related('curso')
        .order_by('-fecha_inicio')
        .first()
    )


def inscribir_en_catalogo(telefono: str, clave: str) -> dict:
    """Inscribe sin borrar otros progresos. Un curso general nuevo por mes."""
    from django.utils import timezone

    from core.inscripcion_curso import inscribir_estudiante_en_curso
    from core.models import Estudiante, ProgresoEstudiante
    from core.nati import normalizar_telefono_whatsapp

    item = item_catalogo(clave)
    curso = curso_catalogo(clave)
    if item is None or curso is None:
        return {'ok': False, 'error': 'sin_curso', 'nombre': (item or {}).get('nombre', '')}
    tel = normalizar_telefono_whatsapp(telefono)
    est = Estudiante.objects.filter(telefono=tel).first()
    if est is None:
        digitos = ''.join(ch for ch in tel if ch.isdigit())[-12:] or '0'
        cedula = f'GEN{digitos}'
        if Estudiante.objects.filter(cedula=cedula).exists():
            cedula = f'GEN{digitos}{curso.id}'[:32]
        est = Estudiante.objects.create(
            nombre='Estudiante eki',
            cedula=cedula[:32],
            telefono=tel,
            cliente=None,
            activo=True,
            acepto_terminos=True,
            fecha_aceptacion_terminos=timezone.now(),
            estado_chat='ACTIVO',
        )
    ocupado = cupo_catalogo_del_mes(est, curso)
    if ocupado is not None:
        return {
            'ok': False,
            'error': 'cupo_mes',
            'nombre': curso.nombre,
            'nombre_activo': ocupado.curso.nombre,
            'curso_activo_id': ocupado.curso_id,
        }
    antes = ProgresoEstudiante.objects.filter(estudiante=est).count()
    progreso, creado = inscribir_estudiante_en_curso(est, curso)
    ctx = dict(est.contexto_temporal or {})
    ctx['curso_activo_id'] = curso.id
    est.contexto_temporal = ctx
    est.save(update_fields=['contexto_temporal'])
    otros = ProgresoEstudiante.objects.filter(estudiante=est).exclude(pk=progreso.pk).count()
    return {
        'ok': True,
        'estudiante_id': est.id,
        'curso_id': curso.id,
        'nombre': curso.nombre,
        'creado': creado,
        'progresos_antes': antes,
        'otros_progresos': otros,
    }
