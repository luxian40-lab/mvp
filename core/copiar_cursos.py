"""
Copiar cursos del cliente Alitic → Analytics (Pruebas).

Estructura completa (módulos, preguntas, secciones, pasos, exámenes, drip, metas, grupos).
Sin estudiantes ni progreso.

Uso desde código:
    from core.copiar_cursos import copiar_cursos_a_pruebas

    resultado = copiar_cursos_a_pruebas(reset=True)
    resultado = copiar_cursos_a_pruebas(solo_curso_id=12)

Uso CLI:
    python manage.py copiar_cursos
    python manage.py copiar_cursos --reset
"""
from __future__ import annotations

from dataclasses import dataclass, field

from django.db import transaction

from core.models import (
    Cliente,
    ConfiguracionDripCliente,
    Curso,
    Examen,
    HabilitacionModuloDripCliente,
    MetaMetricaEmpresa,
    Modulo,
    PasoModulo,
    PreguntaExamen,
    PreguntaModulo,
    SeccionModulo,
)
from core.models_extras import GrupoEstudiantes

# Cliente origen por defecto: Alitic (no confundir con Analytics Pruebas).
CLIENTE_ORIGEN_NOMBRE = 'Alitic'
# Alias histórico en código/tests
CLIENTE_ANALYTICS_ORIGEN_NOMBRE = CLIENTE_ORIGEN_NOMBRE
CLIENTE_PRUEBAS_NIT = '900000002-0'

DESTINO_DEFAULT = {
    'nombre': 'Analytics (Pruebas)',
    'nit': CLIENTE_PRUEBAS_NIT,
    'contacto_principal': 'Equipo Analytics',
    'email': 'analytics-prueba@eki.co',
    'telefono': '573000000198',
    'activo': True,
    'notas_internas': 'Clon de prueba (copiar_cursos). Sin estudiantes.',
}

CLIENTE_COPY_FIELDS = [
    'contacto_principal', 'email', 'telefono', 'activo', 'notas_internas',
    'nombre_bot', 'system_prompt_extra',
]

CURSO_FIELDS = [
    'descripcion', 'emoji', 'duracion_semanas', 'activo', 'orden',
    'usar_gamificacion', 'habilitar_pregunta_abierta_final',
    'enlace_grupo_whatsapp', 'nombre_agente_tutor', 'nombre_agente_asistente',
    'preguntas_ejemplo_ia', 'dias_espera_entre_modulos', 'tiene_formulario_gei',
    'usar_agentes_ia',
]

MODULO_FIELDS = [
    'numero', 'titulo', 'descripcion', 'contenido', 'duracion_dias',
    'habilitado_desde', 'examen_obligatorio', 'modo_entrega', 'video_url',
    'puntaje_minimo_aprobacion', 'facilitador_checkpoint', 'secciones_por_listo',
    'video_resolucion', 'imagen_portada_url', 'archivo_pdf_url',
]


class ClienteOrigenNoEncontrado(LookupError):
    """No existe el cliente origen (Alitic) en la base de datos."""


# Alias para compatibilidad
ClienteAnalyticsNoEncontrado = ClienteOrigenNoEncontrado


@dataclass
class CopiarCursosResult:
    origen: Cliente
    destino: Cliente
    copiados: list[str] = field(default_factory=list)
    omitidos: list[str] = field(default_factory=list)
    reset_borrados: int = 0

    @property
    def total_copiados(self) -> int:
        return len(self.copiados)


def obtener_cliente_analytics_origen(
    *,
    origen_id: int | None = None,
    origen_nombre: str | None = None,
) -> Cliente:
    """Resuelve el cliente Alitic origen (nunca Analytics Pruebas)."""
    if origen_id:
        c = Cliente.objects.filter(pk=origen_id).exclude(nit=CLIENTE_PRUEBAS_NIT).first()
        if not c:
            raise ClienteOrigenNoEncontrado(f'No hay cliente origen con id={origen_id}.')
        return c

    nombre = (origen_nombre or CLIENTE_ORIGEN_NOMBRE).strip()
    base = Cliente.objects.exclude(nit=CLIENTE_PRUEBAS_NIT).exclude(nombre__icontains='Prueba')

    c = base.filter(nombre__iexact=nombre).first()
    if c:
        return c

    c = base.filter(nombre__icontains=nombre).first()
    if c:
        return c

    sugerencias = list(base.filter(nombre__icontains='alitic').values_list('nombre', flat=True)[:5])
    msg = f'No se encontró cliente origen «{nombre}».'
    if sugerencias:
        msg += f' Clientes similares: {", ".join(sugerencias)}.'
    msg += f' Crea el cliente «{CLIENTE_ORIGEN_NOMBRE}» o usa --origen-id / --origen-nombre.'
    raise ClienteOrigenNoEncontrado(msg)


def _asegurar_destino_pruebas(origen: Cliente) -> Cliente:
    destino_data = dict(DESTINO_DEFAULT)
    for f in CLIENTE_COPY_FIELDS:
        if hasattr(origen, f):
            val = getattr(origen, f)
            if val not in (None, ''):
                destino_data[f] = val
    destino, _ = Cliente.objects.update_or_create(
        nit=destino_data['nit'],
        defaults=destino_data,
    )
    return destino


def _copiar_un_curso(
    curso_origen: Curso,
    destino: Cliente,
    origen: Cliente,
    *,
    prefijo: str,
) -> tuple[str | None, str | None]:
    """Retorna (nombre_copiado, nombre_omitido)."""
    nombre_nuevo = curso_origen.nombre
    if prefijo and not nombre_nuevo.startswith(prefijo.strip()):
        nombre_nuevo = f'{prefijo}{curso_origen.nombre}'

    if Curso.objects.filter(cliente=destino, nombre=nombre_nuevo).exists():
        return None, nombre_nuevo

    data = {f: getattr(curso_origen, f) for f in CURSO_FIELDS}
    data['nombre'] = nombre_nuevo
    data['cliente'] = destino
    curso_nuevo = Curso.objects.create(**data)

    map_modulos: dict[int, Modulo] = {}

    for mod in curso_origen.modulos.order_by('numero'):
        mod_data = {f: getattr(mod, f) for f in MODULO_FIELDS}
        mod_data['curso'] = curso_nuevo
        mod_nuevo = Modulo.objects.create(**mod_data)
        map_modulos[mod.id] = mod_nuevo

        for preg in PreguntaModulo.objects.filter(modulo=mod):
            PreguntaModulo.objects.create(
                modulo=mod_nuevo,
                pregunta=preg.pregunta,
                opcion_a=preg.opcion_a,
                opcion_b=preg.opcion_b,
                opcion_c=preg.opcion_c,
                opcion_d=preg.opcion_d,
                respuesta_correcta=preg.respuesta_correcta,
                explicacion=preg.explicacion,
                activa=preg.activa,
            )

        for sec in SeccionModulo.objects.filter(modulo=mod).order_by('orden'):
            sec_nueva = SeccionModulo.objects.create(
                modulo=mod_nuevo,
                orden=sec.orden,
                titulo=sec.titulo,
                activa=sec.activa,
            )
            for paso in PasoModulo.objects.filter(seccion=sec).order_by('orden'):
                PasoModulo.objects.create(
                    modulo=mod_nuevo,
                    seccion=sec_nueva,
                    orden=paso.orden,
                    titulo=paso.titulo,
                    tipo=paso.tipo,
                    contenido=paso.contenido,
                    media_url=paso.media_url,
                    eval_opcion_a=paso.eval_opcion_a,
                    eval_opcion_b=paso.eval_opcion_b,
                    eval_opcion_c=paso.eval_opcion_c,
                    eval_opcion_d=paso.eval_opcion_d,
                    respuesta_correcta=paso.respuesta_correcta,
                    feedback_correcto=paso.feedback_correcto,
                    feedback_incorrecto=paso.feedback_incorrecto,
                    activo=paso.activo,
                    requiere_listo_para_avanzar=paso.requiere_listo_para_avanzar,
                )

    examen_origen = Examen.objects.filter(curso=curso_origen).first()
    if examen_origen:
        examen_nuevo = Examen.objects.create(
            curso=curso_nuevo,
            instrucciones=examen_origen.instrucciones,
            puntaje_minimo=examen_origen.puntaje_minimo,
        )
        for pe in PreguntaExamen.objects.filter(examen=examen_origen):
            PreguntaExamen.objects.create(
                examen=examen_nuevo,
                numero=pe.numero,
                pregunta=pe.pregunta,
                respuesta_correcta=pe.respuesta_correcta,
                puntos=pe.puntos,
            )

    for drip in ConfiguracionDripCliente.objects.filter(cliente=origen, curso=curso_origen):
        ConfiguracionDripCliente.objects.update_or_create(
            cliente=destino,
            curso=curso_nuevo,
            defaults={
                'dias_espera_entre_modulos': drip.dias_espera_entre_modulos,
                'activo': drip.activo,
            },
        )

    for hab in HabilitacionModuloDripCliente.objects.filter(cliente=origen, curso=curso_origen):
        mod_nuevo = map_modulos.get(hab.modulo_id)
        if mod_nuevo:
            HabilitacionModuloDripCliente.objects.update_or_create(
                cliente=destino,
                curso=curso_nuevo,
                modulo=mod_nuevo,
                defaults={
                    'habilitado_desde': hab.habilitado_desde,
                    'activo': hab.activo,
                },
            )

    for meta in MetaMetricaEmpresa.objects.filter(cliente=origen, curso=curso_origen, activa=True):
        MetaMetricaEmpresa.objects.update_or_create(
            cliente=destino,
            curso=curso_nuevo,
            defaults={
                'meta_finalizacion_porcentaje': meta.meta_finalizacion_porcentaje,
                'meta_inicio_porcentaje': meta.meta_inicio_porcentaje,
                'meta_max_no_iniciados_porcentaje': meta.meta_max_no_iniciados_porcentaje,
                'meta_min_lectura_mensajes_porcentaje': meta.meta_min_lectura_mensajes_porcentaje,
                'verde_desde': meta.verde_desde,
                'amarillo_desde': meta.amarillo_desde,
                'activa': True,
            },
        )

    meta_gen = MetaMetricaEmpresa.objects.filter(
        cliente=origen, curso__isnull=True, activa=True,
    ).first()
    if meta_gen and not MetaMetricaEmpresa.objects.filter(cliente=destino, curso__isnull=True).exists():
        MetaMetricaEmpresa.objects.create(
            cliente=destino,
            curso=None,
            meta_finalizacion_porcentaje=meta_gen.meta_finalizacion_porcentaje,
            meta_inicio_porcentaje=meta_gen.meta_inicio_porcentaje,
            meta_max_no_iniciados_porcentaje=meta_gen.meta_max_no_iniciados_porcentaje,
            meta_min_lectura_mensajes_porcentaje=meta_gen.meta_min_lectura_mensajes_porcentaje,
            verde_desde=meta_gen.verde_desde,
            amarillo_desde=meta_gen.amarillo_desde,
            activa=True,
        )

    return nombre_nuevo, None


@transaction.atomic
def copiar_cursos_a_pruebas(
    *,
    reset: bool = False,
    origen_id: int | None = None,
    origen_nombre: str | None = None,
    solo_curso_id: int | None = None,
    curso_ids: list[int] | None = None,
    prefijo: str = '[PRUEBA] ',
) -> CopiarCursosResult:
    """
    Copia cursos del cliente Alitic al entorno Analytics (Pruebas).

    Por defecto origen = cliente «Alitic» (excluye Pruebas).
    """
    origen = obtener_cliente_analytics_origen(
        origen_id=origen_id,
        origen_nombre=origen_nombre,
    )
    destino = _asegurar_destino_pruebas(origen)
    result = CopiarCursosResult(origen=origen, destino=destino)

    if reset:
        result.reset_borrados = Curso.objects.filter(cliente=destino).count()
        Curso.objects.filter(cliente=destino).delete()
        GrupoEstudiantes.objects.filter(cliente=destino).delete()

    qs = Curso.objects.filter(cliente=origen).prefetch_related('modulos')
    if solo_curso_id:
        qs = qs.filter(pk=solo_curso_id)
    elif curso_ids:
        qs = qs.filter(pk__in=curso_ids)

    for curso_origen in qs:
        copiado, omitido = _copiar_un_curso(curso_origen, destino, origen, prefijo=prefijo)
        if copiado:
            result.copiados.append(copiado)
        if omitido:
            result.omitidos.append(omitido)

    for grp in GrupoEstudiantes.objects.filter(cliente=origen):
        GrupoEstudiantes.objects.get_or_create(
            cliente=destino,
            nombre=grp.nombre,
            defaults={'emoji': grp.emoji, 'descripcion': grp.descripcion, 'activo': grp.activo},
        )

    return result
