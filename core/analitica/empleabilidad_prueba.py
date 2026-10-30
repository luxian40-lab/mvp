"""Utilidades para armar y simular pruebas de empleabilidad territorial."""

from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone

from core.models import AliadoEmpleabilidad, Cliente, Estudiante, MisionEmpleabilidad
from core.views import _procesar_ubicacion_empleabilidad


ALIADOS_DEMO = (
    {
        'nombre_empresa': 'Aliado demo — Parque central',
        'codigo_secreto': 'EKI-DEMO-01',
        'indicacion_sector': 'entrada principal del parque',
        'offset_lat': 0.0,
        'offset_lng': 0.0,
        'prioridad': 5,
    },
    {
        'nombre_empresa': 'Aliado demo — Comercio local',
        'codigo_secreto': 'EKI-DEMO-02',
        'indicacion_sector': 'plazoleta del mercado',
        'offset_lat': 0.00045,
        'offset_lng': 0.00012,
        'prioridad': 4,
    },
    {
        'nombre_empresa': 'Aliado demo — Centro formativo',
        'codigo_secreto': 'EKI-DEMO-03',
        'indicacion_sector': 'segundo piso del centro',
        'offset_lat': 0.0018,
        'offset_lng': -0.0003,
        'prioridad': 3,
    },
)


@dataclass
class ResultadoSetupEmpleabilidad:
    cliente: Cliente
    aliados: list[AliadoEmpleabilidad]
    estudiante: Estudiante | None
    portal_url: str
    admin_aliados_url: str
    admin_misiones_url: str


def _portal_productos_con_empleabilidad(raw: str | None) -> str:
    partes = [p.strip() for p in (raw or '').split(',') if p.strip()]
    vistos: set[str] = set()
    out: list[str] = []
    for p in partes:
        if p not in vistos:
            out.append(p)
            vistos.add(p)
    if 'empleabilidad' not in vistos:
        out.append('empleabilidad')
    return ','.join(out)


def configurar_cliente_empleabilidad(
    cliente: Cliente,
    *,
    radio_metros: int = 1500,
    activar_portal: bool = True,
) -> list[str]:
    """Activa flags del cliente. Devuelve lista de cambios aplicados."""
    cambios: list[str] = []
    if not cliente.empleabilidad_exploracion_activa:
        cliente.empleabilidad_exploracion_activa = True
        cambios.append('empleabilidad_exploracion_activa=True')

    if int(cliente.empleabilidad_radio_metros or 800) < radio_metros:
        cliente.empleabilidad_radio_metros = radio_metros
        cambios.append(f'empleabilidad_radio_metros={radio_metros}')

    if activar_portal:
        nuevo = _portal_productos_con_empleabilidad(cliente.portal_productos)
        if nuevo != (cliente.portal_productos or ''):
            cliente.portal_productos = nuevo
            cambios.append(f'portal_productos={nuevo}')

    if cambios:
        cliente.save()
    return cambios


def crear_aliados_demo(
    cliente: Cliente,
    *,
    lat_base: float,
    lng_base: float,
    reemplazar: bool = False,
) -> list[AliadoEmpleabilidad]:
    """Crea o actualiza 3 aliados de prueba alrededor de un punto."""
    if reemplazar:
        AliadoEmpleabilidad.objects.filter(
            cliente=cliente,
            codigo_secreto__startswith='EKI-DEMO-',
        ).delete()

    hoy = timezone.localdate()
    aliados: list[AliadoEmpleabilidad] = []
    for spec in ALIADOS_DEMO:
        lat = lat_base + spec['offset_lat']
        lng = lng_base + spec['offset_lng']
        aliado, _ = AliadoEmpleabilidad.objects.update_or_create(
            cliente=cliente,
            codigo_secreto=spec['codigo_secreto'],
            defaults={
                'nombre_empresa': spec['nombre_empresa'],
                'latitud': lat,
                'longitud': lng,
                'vacantes_activas': True,
                'cupos_disponibles': 10,
                'prioridad': spec['prioridad'],
                'indicacion_sector': spec['indicacion_sector'],
                'vigencia_desde': hoy,
                'vigencia_hasta': None,
            },
        )
        aliados.append(aliado)
    return aliados


def preparar_estudiante_prueba(estudiante: Estudiante) -> None:
    """Marca radar activo en contexto (opcional para UX; la ubicación funciona igual)."""
    ctx = estudiante.contexto_temporal or {}
    ctx['radar_empleabilidad_activo'] = True
    ctx['empleabilidad_habilitado_en'] = timezone.now().isoformat()
    estudiante.contexto_temporal = ctx
    if estudiante.estado_chat != 'ACTIVO':
        estudiante.estado_chat = 'ACTIVO'
    estudiante.save(update_fields=['contexto_temporal', 'estado_chat'])


def simular_ubicacion_whatsapp(estudiante: Estudiante, lat: float, lng: float) -> str:
    """Misma lógica que el webhook Twilio al recibir ubicación."""
    return _procesar_ubicacion_empleabilidad(estudiante, lat, lng)


def completar_mision_con_codigo(estudiante: Estudiante, codigo: str) -> tuple[bool, str]:
    """Valida código como el chat WhatsApp (sin enviar mensaje Twilio)."""
    from core.gamificacion import Badge, BadgeEstudiante, PerfilGamificacion

    ctx = estudiante.contexto_temporal or {}
    aliado_id = ctx.get('aliado_empleabilidad_objetivo_id')
    mision_id = ctx.get('mision_empleabilidad_id')
    if not aliado_id:
        return False, 'No hay misión abierta. Envía ubicación primero.'

    aliado = AliadoEmpleabilidad.objects.filter(id=aliado_id, vacantes_activas=True).first()
    if not aliado:
        return False, 'Aliado objetivo no encontrado.'

    if codigo.strip().lower() != str(aliado.codigo_secreto).strip().lower():
        mision = None
        if mision_id:
            mision = MisionEmpleabilidad.objects.filter(id=mision_id, estudiante=estudiante).first()
        if mision and mision.estado == 'descubierta':
            mision.estado = 'reclamada'
            mision.fecha_reclamada = timezone.now()
            mision.save(update_fields=['estado', 'fecha_reclamada'])
        return False, 'Código incorrecto.'

    perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
    puntos = int(getattr(estudiante.cliente, 'empleabilidad_puntos_validacion', 30) or 30)
    perfil.agregar_puntos(puntos, f'Radar Empleabilidad: {aliado.nombre_empresa}')
    badge = Badge.objects.filter(tipo='ESPECIAL', activo=True, nombre__icontains='emple').first()
    if badge:
        BadgeEstudiante.objects.get_or_create(estudiante=estudiante, badge=badge)

    mision = None
    if mision_id:
        mision = MisionEmpleabilidad.objects.filter(id=mision_id, estudiante=estudiante).first()
    if mision and mision.estado != 'completada':
        mision.estado = 'completada'
        mision.codigo_validado = True
        mision.puntos_otorgados = puntos
        mision.fecha_completada = timezone.now()
        mision.save(update_fields=['estado', 'codigo_validado', 'puntos_otorgados', 'fecha_completada'])

    ctx['ultimo_match_empleabilidad_aliado_id'] = aliado.id
    ctx['ultimo_match_empleabilidad_fecha'] = timezone.now().isoformat()
    estudiante.contexto_temporal = ctx
    estudiante.estado_onboarding = 'curso_finalizado'
    estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
    return True, f'Misión completada con {aliado.nombre_empresa} (+{puntos} pts).'


def setup_prueba_empleabilidad(
    cliente: Cliente,
    *,
    lat_base: float = 4.926,
    lng_base: float = -74.173,
    radio_metros: int = 1500,
    telefono: str | None = None,
    activar_portal: bool = True,
    reemplazar_aliados: bool = False,
    base_url: str = 'http://eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com',
) -> ResultadoSetupEmpleabilidad:
    configurar_cliente_empleabilidad(cliente, radio_metros=radio_metros, activar_portal=activar_portal)
    aliados = crear_aliados_demo(cliente, lat_base=lat_base, lng_base=lng_base, reemplazar=reemplazar_aliados)

    estudiante = None
    if telefono:
        estudiante = Estudiante.objects.filter(telefono=telefono, activo=True).select_related('cliente').first()
        if estudiante:
            preparar_estudiante_prueba(estudiante)

    return ResultadoSetupEmpleabilidad(
        cliente=cliente,
        aliados=aliados,
        estudiante=estudiante,
        portal_url=f'{base_url.rstrip("/")}/portal/empleabilidad/',
        admin_aliados_url=f'{base_url.rstrip("/")}/admin/learning/aliadoempleabilidad/',
        admin_misiones_url=f'{base_url.rstrip("/")}/admin/learning/misionempleabilidad/',
    )
