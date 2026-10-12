"""Listado CRM de Estudiantes: cifras, estado, actividad y última nota."""
from __future__ import annotations

import hashlib
from datetime import timedelta

from django.db.models import (
    BooleanField,
    Count,
    DateTimeField,
    Exists,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.models import (
    Curso,
    Modulo,
    ModuloCompletado,
    NotaEstudiante,
    ProgresoEstudiante,
    WhatsappLog,
)
from core.models_certificados import Certificado

DIAS_SIN_AVANCE = 14
CACHE_SEGUNDOS = 60

TONOS_ORG = (
    '#5c4a3a',
    '#3e6b4a',
    '#8a5a44',
    '#4d5e68',
    '#7a6230',
    '#5c4d6a',
    '#3f5c55',
    '#6b5344',
)
TONO_SIN_ORG = '#8a6a2f'

_ESTADO_TEXTO = {
    'completado': 'Completado',
    'habeas': 'Habeas pendiente',
    'sin_actividad': 'Sin actividad',
    'sin_iniciar': 'Sin iniciar',
    'activo': 'Activo',
}


def tono_organizacion(cliente_id):
    if not cliente_id:
        return TONO_SIN_ORG
    return TONOS_ORG[int(cliente_id) % len(TONOS_ORG)]


def iniciales(nombre):
    partes = [parte for parte in (nombre or '').split() if parte]
    if not partes:
        return '?'
    if len(partes) == 1:
        return partes[0][:1].upper()
    return (partes[0][:1] + partes[1][:1]).upper()


def texto_actividad(cuando, ahora=None):
    if cuando is None:
        return 'nunca escribió'
    ahora = ahora or timezone.now()
    if timezone.is_aware(cuando):
        cuando = timezone.localtime(cuando)
        hoy = timezone.localtime(ahora).date()
    else:
        hoy = ahora.date()
    dias = (hoy - cuando.date()).days
    if dias <= 0:
        return 'hoy'
    if dias == 1:
        return 'hace 1 día'
    return f'hace {dias} días'


def clasificar_estado(
    *,
    estado_chat,
    completo,
    fecha_avance,
    n_completados=0,
    ahora=None,
    ultima_entrada=None,
):
    """Un chip. Completado manda. Sin actividad es el mismo corte de 14 días que la cifra."""
    del ultima_entrada
    ahora = ahora or timezone.now()
    if completo:
        slug = 'completado'
    elif (estado_chat or '') == 'ESPERANDO_HABEAS_DATA':
        slug = 'habeas'
    elif fecha_avance is not None and fecha_avance < ahora - timedelta(days=DIAS_SIN_AVANCE):
        slug = 'sin_actividad'
    elif fecha_avance is None and not n_completados:
        slug = 'sin_iniciar'
    else:
        slug = 'activo'
    return slug, _ESTADO_TEXTO[slug]


def _ultimo_progreso(curso_param):
    qs = ProgresoEstudiante.objects.filter(estudiante_id=OuterRef('pk'))
    curso = (curso_param or '').strip()
    if curso == 'sin_curso':
        qs = qs.none()
    elif curso.isdigit():
        qs = qs.filter(curso_id=int(curso))
    return qs.order_by(F('fecha_ultimo_avance').desc(nulls_last=True), '-pk')


def _cuenta_subquery(qs):
    return Subquery(
        qs.order_by().values('progreso').annotate(n=Count('pk')).values('n')[:1],
        output_field=IntegerField(),
    )


def anotar_progresos_lista():
    """Prefetch de la página: completados y publicados, sin una consulta por fila."""
    publicados = Modulo.objects.filter(curso_id=OuterRef('curso_id')).filter(
        Q(curso__modo_aula=Curso.MODO_AULA_CLASES) | Q(publicado_wa=True)
    )
    return ProgresoEstudiante.objects.select_related('curso', 'modulo_actual').annotate(
        _n_mods=Count('curso__modulos', distinct=True),
        _n_completados=Coalesce(
            _cuenta_subquery(ModuloCompletado.objects.filter(progreso_id=OuterRef('pk'))),
            0,
        ),
        _n_publicados=Coalesce(
            Subquery(
                publicados.order_by().values('curso').annotate(n=Count('pk', distinct=True)).values('n')[:1],
                output_field=IntegerField(),
            ),
            0,
        ),
    ).order_by(F('fecha_ultimo_avance').desc(nulls_last=True), '-pk')


def firma_nota(nombre, apellido, usuario):
    visible = ' '.join(
        parte for parte in ((nombre or '').strip(), (apellido or '').strip()) if parte
    ).strip()
    return visible or (usuario or '').strip()


def anotar_ultima_nota(qs):
    """La nota más reciente, en la misma consulta de la página."""
    if '_nota_texto' in qs.query.annotations:
        return qs
    ultima = NotaEstudiante.objects.filter(estudiante_id=OuterRef('pk')).order_by('-creado', '-pk')
    return qs.annotate(
        _nota_texto=Subquery(ultima.values('texto')[:1]),
        _nota_nombre=Subquery(ultima.values('autor__first_name')[:1]),
        _nota_apellido=Subquery(ultima.values('autor__last_name')[:1]),
        _nota_usuario=Subquery(ultima.values('autor__username')[:1]),
    )


def anotar_ultima_entrada(qs):
    if '_crm_ultima' in qs.query.annotations:
        return qs
    ultima = (
        WhatsappLog.objects.filter(estudiante_id=OuterRef('pk'), tipo='INCOMING')
        .order_by('-fecha')
        .values('fecha')[:1]
    )
    return qs.annotate(_crm_ultima=Subquery(ultima, output_field=DateTimeField()))


def filtrar_sin_avanzar(qs, curso_param=None, ahora=None):
    """Inscripción visible sin completar y sin avance en 14 días, o sin inscripción."""
    ahora = ahora or timezone.now()
    limite = ahora - timedelta(days=DIAS_SIN_AVANCE)
    latest = _ultimo_progreso(curso_param)
    diploma = Certificado.objects.filter(
        estudiante_id=OuterRef('pk'),
        curso_id=Subquery(latest.values('curso_id')[:1]),
        emitido=True,
        anulado=False,
    )
    return (
        qs.annotate(
            _crm_cuando=Subquery(latest.values('fecha_ultimo_avance')[:1], output_field=DateTimeField()),
            _crm_hecho=Subquery(latest.values('completado')[:1], output_field=BooleanField()),
            _crm_diploma=Exists(diploma),
        )
        .filter(_crm_diploma=False)
        .filter(Q(_crm_hecho=False) | Q(_crm_hecho__isnull=True))
        .exclude(estado_chat='ESPERANDO_HABEAS_DATA')
        .filter(_crm_cuando__lt=limite)
    )


def filtrar_estado_crm(qs, slug, curso_param=None, ahora=None):
    """La misma clasificación que el chip, para localizar a esas personas en la tabla."""
    if slug not in _ESTADO_TEXTO:
        return qs
    ahora = ahora or timezone.now()
    ids = []
    for fila in _filas(qs, curso_param):
        estado, _texto = clasificar_estado(
            estado_chat=fila['estado_chat'],
            completo=fila['completo'],
            fecha_avance=fila['cuando'],
            n_completados=fila['n_completados'],
            ahora=ahora,
        )
        if estado == slug:
            ids.append(fila['pk'])
    if not ids:
        return qs.none()
    return qs.filter(pk__in=ids)


def org_en_request(get):
    if (get.get('cliente__isnull') or '') in ('True', 'true', '1'):
        return 'sin'
    exacto = (get.get('cliente__id__exact') or get.get('cliente__id') or '').strip()
    if exacto.isdigit():
        return int(exacto)
    return None


def clave_crm(request):
    partes = [str(getattr(request.user, 'pk', 0))]
    for clave, valores in sorted(request.GET.lists()):
        if clave in ('page', 'crm_refresh'):
            continue
        for valor in valores:
            partes.append(f'{clave}={valor}')
    resumen = hashlib.sha256('|'.join(partes).encode()).hexdigest()[:24]
    return f'eki_crm_est_{resumen}'


_ANOTACIONES_DE_PAGINA = (
    '_crm_ultima',
    '_nota_texto',
    '_nota_nombre',
    '_nota_apellido',
    '_nota_usuario',
)


def _plano(qs):
    """Sin el prefetch de la página ni la última nota: las cifras no los necesitan."""
    plano = qs.all()
    plano.query = qs.query.clone()
    for nombre in _ANOTACIONES_DE_PAGINA:
        plano.query.annotations.pop(nombre, None)
    plano._prefetch_related_lookups = ()
    return plano.order_by().select_related(None)


def _es_mas_reciente(nuevo, viejo):
    """Misma prioridad que _ultimo_progreso: fecha desc, nulos al final, pk desc."""
    fn = nuevo['fecha_ultimo_avance']
    fv = viejo['fecha_ultimo_avance']
    if fn is None and fv is None:
        return nuevo['pk'] > viejo['pk']
    if fn is None:
        return False
    if fv is None:
        return True
    if fn != fv:
        return fn > fv
    return nuevo['pk'] > viejo['pk']


def _filas(qs, curso_param):
    """Una fila por estudiante, con consultas planas. No recorre el admin otra vez."""
    personas = list(
        _plano(qs).values('pk', 'estado_chat', 'cliente_id', 'cliente__nombre').distinct()
    )
    est_ids = [fila['pk'] for fila in personas] or [-1]
    curso = (curso_param or '').strip()
    progresos = []
    if curso != 'sin_curso':
        base = ProgresoEstudiante.objects.filter(estudiante_id__in=est_ids)
        if curso.isdigit():
            base = base.filter(curso_id=int(curso))
        progresos = list(base.values(
            'pk',
            'estudiante_id',
            'curso_id',
            'completado',
            'fecha_ultimo_avance',
            'curso__nombre',
        ))
    por_estudiante = {}
    for progreso in progresos:
        por_estudiante.setdefault(progreso['estudiante_id'], []).append(progreso)
    elegidos = {}
    for est_id, opciones in por_estudiante.items():
        elegido = None
        for opcion in opciones:
            if elegido is None or _es_mas_reciente(opcion, elegido):
                elegido = opcion
        elegidos[est_id] = elegido
    prog_ids = [fila['pk'] for fila in elegidos.values() if fila] or [-1]
    curso_ids = [fila['curso_id'] for fila in elegidos.values() if fila and fila['curso_id']] or [-1]
    completados = {
        prog_id: n
        for prog_id, n in (
            ModuloCompletado.objects.filter(progreso_id__in=prog_ids)
            .values('progreso_id')
            .annotate(n=Count('pk'))
            .values_list('progreso_id', 'n')
        )
    }
    publicados = {}
    for fila_mod in (
        Modulo.objects.filter(curso_id__in=curso_ids)
        .values('curso_id', 'curso__modo_aula')
        .annotate(
            total=Count('pk'),
            publicados=Count('pk', filter=Q(publicado_wa=True)),
        )
    ):
        if fila_mod['curso__modo_aula'] == Curso.MODO_AULA_CLASES:
            publicados[fila_mod['curso_id']] = fila_mod['total']
        else:
            publicados[fila_mod['curso_id']] = fila_mod['publicados']
    diplomas = set(
        Certificado.objects.filter(
            estudiante_id__in=est_ids,
            emitido=True,
            anulado=False,
        ).values_list('estudiante_id', 'curso_id')
    )
    filas = []
    for persona in personas:
        elegido = elegidos.get(persona['pk'])
        curso_id = elegido['curso_id'] if elegido else None
        persona['prog_id'] = elegido['pk'] if elegido else None
        persona['curso_id_crm'] = curso_id
        persona['curso_nombre'] = elegido['curso__nombre'] if elegido else None
        persona['hecho'] = elegido['completado'] if elegido else None
        persona['cuando'] = elegido['fecha_ultimo_avance'] if elegido else None
        persona['n_completados'] = completados.get(persona['prog_id'], 0)
        persona['n_publicados'] = publicados.get(curso_id, 0)
        persona['completo'] = bool(persona['hecho']) or (persona['pk'], curso_id) in diplomas
        persona['_crm_ultima'] = None
        filas.append(persona)
    return filas


def _pct(fila):
    """0 si no tiene curso. El promedio de la organización incluye a toda la lista."""
    if not fila.get('curso_id_crm'):
        return 0
    if fila['completo']:
        return 100
    total = fila['n_publicados'] or 0
    if total <= 0:
        return 0
    return int(fila['n_completados'] * 100 / total)


def _sin_actividad(fila, ahora):
    if fila['completo'] or (fila.get('estado_chat') or '') == 'ESPERANDO_HABEAS_DATA':
        return False
    cuando = fila['cuando']
    if cuando is None:
        return False
    return cuando < ahora - timedelta(days=DIAS_SIN_AVANCE)


def _promedio(filas):
    if not filas:
        return 0
    total = sum(_pct(fila) for fila in filas)
    return int(total / len(filas) + 0.5)


def _url(request, cambios=None, quitar_cliente=False, quitar_curso=False):
    params = request.GET.copy()
    params.pop('page', None)
    params.pop('crm_refresh', None)
    if quitar_cliente:
        for clave in list(params):
            if clave.startswith('cliente'):
                params.pop(clave, None)
    if quitar_curso:
        params.pop('curso', None)
    for clave, valor in (cambios or {}).items():
        if valor is None:
            params.pop(clave, None)
        else:
            params[clave] = str(valor)
    encoded = params.urlencode()
    if encoded:
        return f'{request.path}?{encoded}'
    return request.path


def _opciones(filas, request, elegida):
    grupos = {}
    for fila in filas:
        clave = fila['cliente_id'] if fila['cliente_id'] else 'sin'
        grupos.setdefault(clave, []).append(fila)
    opciones = [{
        'nombre': 'Todas',
        'n': len(filas),
        'avance': _promedio(filas),
        'url': _url(request, quitar_cliente=True, quitar_curso=True),
        'activa': elegida is None,
        'sin': False,
    }]
    orgs = []
    for clave, personas in grupos.items():
        if clave == 'sin':
            continue
        nombre = personas[0]['cliente__nombre'] or 'Organización'
        orgs.append({
            'nombre': nombre,
            'n': len(personas),
            'avance': _promedio(personas),
            'url': _url(
                request,
                {'cliente__id__exact': clave},
                quitar_cliente=True,
                quitar_curso=True,
            ),
            'activa': elegida == clave,
            'sin': False,
        })
    orgs.sort(key=lambda item: item['nombre'].lower())
    opciones.extend(orgs)
    sin = grupos.get('sin', [])
    opciones.append({
        'nombre': 'Sin organización',
        'n': len(sin),
        'avance': _promedio(sin),
        'url': _url(
            request,
            {'cliente__isnull': 'True'},
            quitar_cliente=True,
            quitar_curso=True,
        ),
        'activa': elegida == 'sin',
        'sin': True,
    })
    return opciones


def _etiqueta_elegida(opciones, elegida):
    for opcion in opciones:
        if opcion['activa']:
            return opcion['nombre'], opcion['n']
    return 'Todas', sum(opcion['n'] for opcion in opciones if opcion['nombre'] == 'Todas')


def _panel_cursos(est_ids):
    if not est_ids:
        return []
    progresos = ProgresoEstudiante.objects.filter(
        estudiante_id__in=est_ids,
    ).values_list('estudiante_id', 'curso_id', 'curso__nombre', 'completado')
    diplomas = set(
        Certificado.objects.filter(
            estudiante_id__in=est_ids,
            emitido=True,
            anulado=False,
        ).values_list('estudiante_id', 'curso_id')
    )
    cursos = {}
    for est_id, curso_id, nombre, hecho in progresos:
        if not curso_id:
            continue
        item = cursos.setdefault(curso_id, {'nombre': nombre or 'Curso', 'ids': set(), 'ok': set()})
        item['ids'].add(est_id)
        if hecho or (est_id, curso_id) in diplomas:
            item['ok'].add(est_id)
    panel = []
    for curso_id, item in cursos.items():
        total = len(item['ids'])
        ok = len(item['ok'])
        pct = int(round(ok * 100 / total)) if total else 0
        panel.append({
            'id': curso_id,
            'nombre': item['nombre'],
            'texto': f'{ok} de {total} completaron',
            'pct': pct,
            'n': total,
        })
    panel.sort(key=lambda item: item['nombre'].lower())
    return panel


def _pestanas(request, est_ids, panel):
    todos = _url(request, {'curso': None})
    curso_actual = (request.GET.get('curso') or '').strip()
    pestanas = [{
        'nombre': 'Todos',
        'n': len(est_ids),
        'url': todos,
        'activa': not curso_actual,
    }]
    for curso in panel:
        pestanas.append({
            'nombre': curso['nombre'],
            'n': curso['n'],
            'url': _url(request, {'curso': curso['id']}),
            'activa': curso_actual == str(curso['id']),
        })
    return pestanas


def _queryset_crm(modeladmin, request, cl, *, sin_cliente=False, sin_curso=False):
    """El queryset del listado ya armado, sin volver a construir el admin."""
    from django.contrib.admin.utils import (
        build_q_object_from_lookup_parameters,
        prepare_lookup_value,
    )
    from django.contrib.admin.views.main import ERROR_FLAG, IGNORED_PARAMS, PAGE_VAR

    saltar = set()
    if sin_cliente:
        saltar.update({'cliente__id__exact', 'cliente__isnull', 'cliente__id'})
    if sin_curso:
        saltar.add('curso')
    ignorar = set(IGNORED_PARAMS) | {PAGE_VAR, ERROR_FLAG, 'crm_refresh'}
    qs = cl.root_queryset
    for spec in cl.filter_specs:
        esperados = set(spec.expected_parameters())
        if esperados and (esperados <= saltar or 'eki_crm_estado' in esperados):
            continue
        nuevo = spec.queryset(request, qs)
        if nuevo is not None:
            qs = nuevo
    restantes = {}
    for clave, valores in request.GET.lists():
        if clave in ignorar:
            continue
        restantes[clave] = valores
    for spec in cl.filter_specs:
        for nombre in spec.expected_parameters():
            restantes.pop(nombre, None)
    if restantes:
        limpio = {
            clave: prepare_lookup_value(clave, valores)
            for clave, valores in restantes.items()
        }
        qs = qs.filter(build_q_object_from_lookup_parameters(limpio))
    # La búsqueda solo recorta la tabla. Los KPI siguen siendo de toda la organización.
    return qs


def armar_crm(modeladmin, request, cl, ahora=None):
    ahora = ahora or timezone.now()
    elegida = org_en_request(request.GET)
    qs = _queryset_crm(modeladmin, request, cl, sin_cliente=True, sin_curso=True)
    filas = _filas(qs, curso_param=None)
    if elegida == 'sin':
        del_org = [fila for fila in filas if not fila['cliente_id']]
    elif isinstance(elegida, int):
        del_org = [fila for fila in filas if fila['cliente_id'] == elegida]
    else:
        del_org = filas
    curso_param = (request.GET.get('curso') or '').strip()
    if curso_param:
        visibles = _filas(
            _queryset_crm(modeladmin, request, cl),
            curso_param,
        )
    else:
        visibles = del_org
    opciones = _opciones(filas, request, elegida)
    nombre, conteo = _etiqueta_elegida(opciones, elegida)
    estado_actual = (request.GET.get('eki_crm_estado') or '').strip()
    estados = {slug: 0 for slug in _ESTADO_TEXTO}
    for fila in visibles:
        slug, _texto = clasificar_estado(
            estado_chat=fila['estado_chat'],
            ultima_entrada=fila['_crm_ultima'],
            completo=fila['completo'],
            fecha_avance=fila['cuando'],
            n_completados=fila['n_completados'],
            ahora=ahora,
        )
        estados[slug] += 1
    est_ids = [fila['pk'] for fila in del_org]
    panel = _panel_cursos(est_ids) if elegida is not None else []
    sin_n = sum(1 for fila in visibles if _sin_actividad(fila, ahora))
    return {
        'elegida_nombre': nombre,
        'elegida_n': conteo if elegida is None else len(del_org),
        'opciones': opciones,
        'avance': _promedio(visibles),
        'completaron': sum(1 for fila in visibles if fila['completo']),
        'sin_actividad': sin_n,
        'habeas': sum(1 for fila in visibles if (fila['estado_chat'] or '') == 'ESPERANDO_HABEAS_DATA'),
        'estados': [
            {
                'slug': slug,
                'label': texto,
                'n': estados[slug],
                'activa': estado_actual == slug,
                'url': _url(
                    request,
                    {'eki_crm_estado': None if estado_actual == slug else slug},
                ),
            }
            for slug, texto in _ESTADO_TEXTO.items()
        ],
        'cursos': panel,
        'pestanas': _pestanas(request, est_ids, panel) if elegida is not None else [],
        'sin_avanzar_n': sin_n,
        'sin_avanzar_url': _url(request, {'eki_sin_avanzar': '1'}),
        'actualizar_url': _url(request, {'crm_refresh': '1'}),
        'org_elegida': elegida is not None,
    }


def datos_crm(modeladmin, request, cl):
    from django.core.cache import cache

    clave = clave_crm(request)
    try:
        guardado = cache.get(clave)
    except Exception:
        guardado = None
    if guardado is not None:
        return guardado
    payload = armar_crm(modeladmin, request, cl)
    try:
        cache.set(clave, payload, CACHE_SEGUNDOS)
    except Exception:
        pass
    return payload
