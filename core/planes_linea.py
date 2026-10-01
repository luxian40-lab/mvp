"""Planes comerciales de la línea Meta: lo único que se vende a clientes.

OP1 = 1 curso al mes + asesor (30 preguntas).
OP2 = 2 cursos al mes, sin asesor.
OP3 = asesor con 60 preguntas al mes, sin cursos.

El plan sale de la persona (SandboxCanalSesion.plan), si no tiene de su
grupo (GrupoEstudiantes.plan_linea_meta) y si el grupo no tiene, de su
organización (Cliente.plan_linea_meta). Sin plan no hay cursos nuevos ni asesor;
los cursos que ya van en curso siguen funcionando.
"""
from __future__ import annotations

from dataclasses import dataclass

PLAN_CURSO_ASESOR = 'curso_asesor'
PLAN_DOS_CURSOS = 'dos_cursos'
PLAN_ASESOR_60 = 'asesor_60'

PLAN_CHOICES = [
    (PLAN_CURSO_ASESOR, 'OP1 — 1 curso al mes + asesor (30 preguntas)'),
    (PLAN_DOS_CURSOS, 'OP2 — 2 cursos al mes'),
    (PLAN_ASESOR_60, 'OP3 — asesor, 60 preguntas al mes'),
]


@dataclass(frozen=True)
class PlanLinea:
    clave: str
    cursos_mes: int
    preguntas_mes: int

    @property
    def activo(self) -> bool:
        return bool(self.clave)

    @property
    def incluye_cursos(self) -> bool:
        return self.cursos_mes > 0

    @property
    def incluye_asesor(self) -> bool:
        return self.preguntas_mes > 0


_PLANES = {
    PLAN_CURSO_ASESOR: PlanLinea(PLAN_CURSO_ASESOR, cursos_mes=1, preguntas_mes=30),
    PLAN_DOS_CURSOS: PlanLinea(PLAN_DOS_CURSOS, cursos_mes=2, preguntas_mes=0),
    PLAN_ASESOR_60: PlanLinea(PLAN_ASESOR_60, cursos_mes=0, preguntas_mes=60),
}
SIN_PLAN = PlanLinea('', cursos_mes=0, preguntas_mes=0)


def plan_por_clave(clave: str | None) -> PlanLinea:
    return _PLANES.get((clave or '').strip(), SIN_PLAN)


def _plan_default() -> PlanLinea:
    from django.conf import settings

    return plan_por_clave(getattr(settings, 'LINEA_META_PLAN_DEFAULT', ''))


def _plan_organizacion(telefono: str) -> str:
    from datetime import date

    from django.db.models import Q

    from core.models import Estudiante

    return (
        Estudiante.objects.filter(
            telefono=telefono,
            cliente__activo=True,
            cliente__plan_linea_meta__gt='',
        )
        .filter(
            Q(cliente__fecha_fin_suscripcion__isnull=True)
            | Q(cliente__fecha_fin_suscripcion__gte=date.today())
        )
        .order_by('-cliente_id')
        .values_list('cliente__plan_linea_meta', flat=True)
        .first()
        or ''
    )


def _plan_demo_twilio() -> PlanLinea:
    from django.conf import settings

    return plan_por_clave(getattr(settings, 'LINEA_DEMO_TWILIO_PLAN', PLAN_CURSO_ASESOR))


def _plan_grupo(telefono: str) -> str:
    """Grupo activo con plan. Si la persona está en varios, gana el creado de último."""
    from datetime import date

    from django.db.models import Q

    from core.models_extras import GrupoEstudiantes

    return (
        GrupoEstudiantes.objects.filter(
            activo=True,
            plan_linea_meta__gt='',
            estudiantes__telefono=telefono,
            cliente__activo=True,
        )
        .filter(
            Q(cliente__fecha_fin_suscripcion__isnull=True)
            | Q(cliente__fecha_fin_suscripcion__gte=date.today())
        )
        .order_by('-fecha_creacion', '-id')
        .values_list('plan_linea_meta', flat=True)
        .first()
        or ''
    )


def resolver_plan(telefono: str) -> PlanLinea:
    """
    Persona > grupo (suscripción vigente) > organización > LINEA_META_PLAN_DEFAULT.
    Con SANDBOX_PROVEEDOR=twilio (canal de demos) no se cobra: persona > LINEA_DEMO_TWILIO_PLAN.
    """
    from core.models import SandboxCanalSesion
    from core.nati import normalizar_telefono_whatsapp
    from core.sandbox_canal import sandbox_via_meta

    tel = normalizar_telefono_whatsapp(telefono or '')
    if not tel:
        return SIN_PLAN
    propio = (
        SandboxCanalSesion.objects.filter(telefono=tel).values_list('plan', flat=True).first()
        or ''
    )
    if propio:
        return plan_por_clave(propio)
    if not sandbox_via_meta():
        return _plan_demo_twilio()
    grupo = _plan_grupo(tel)
    if grupo:
        return plan_por_clave(grupo)
    org = _plan_organizacion(tel)
    if org:
        return plan_por_clave(org)
    return _plan_default()


def inicio_mes_local():
    from django.utils import timezone

    return timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def preguntas_usadas_mes(telefono: str) -> int:
    from core.models import SandboxCanalSesion

    fila = (
        SandboxCanalSesion.objects.filter(telefono=telefono)
        .values('preguntas_mes', 'preguntas_mes_desde')
        .first()
    )
    if not fila or fila['preguntas_mes_desde'] != inicio_mes_local().date():
        return 0
    return fila['preguntas_mes']


def registrar_pregunta_asesor(telefono: str) -> None:
    """Suma una pregunta del mes; el primer registro de un mes nuevo arranca en 1."""
    from django.db.models import F

    from core.models import SandboxCanalSesion

    mes = inicio_mes_local().date()
    sumadas = SandboxCanalSesion.objects.filter(
        telefono=telefono, preguntas_mes_desde=mes
    ).update(preguntas_mes=F('preguntas_mes') + 1)
    if not sumadas:
        SandboxCanalSesion.objects.filter(telefono=telefono).update(
            preguntas_mes=1, preguntas_mes_desde=mes
        )


def cursos_iniciados_en_el_mes(telefono: str, *, excluir_curso_id: int | None = None):
    """Cursos (generales eki o de la organización) que la persona empezó este mes."""
    from core.models import ProgresoEstudiante
    from core.nati import normalizar_telefono_whatsapp

    qs = ProgresoEstudiante.objects.filter(
        estudiante__telefono=normalizar_telefono_whatsapp(telefono or ''),
        fecha_inicio__gte=inicio_mes_local(),
    )
    if excluir_curso_id:
        qs = qs.exclude(curso_id=excluir_curso_id)
    return qs.select_related('curso').order_by('-fecha_inicio')


def texto_menu_plan(plan: PlanLinea) -> str:
    if plan.clave == PLAN_DOS_CURSOS:
        oferta = "podrá acceder a dos cursos de formación durante el mes de su escogencia."
    elif plan.clave == PLAN_ASESOR_60:
        oferta = (
            f"podrá consultar al asesor, con un máximo de {plan.preguntas_mes} "
            "preguntas durante el mes."
        )
    else:
        oferta = (
            "podrá acceder a un curso de formación durante el próximo mes de su "
            f"escogencia y al asesor, con un máximo de {plan.preguntas_mes} "
            "preguntas durante el mes."
        )
    return (
        f"A través de este menú {oferta}\n\n"
        "Queremos que fortalezca sus competencias y actualice sus conocimientos "
        "para mejorar su entorno y el de los demás. Dé su mejor esfuerzo y nunca "
        "deje de aprender.\n\n"
        "Elija una opción:"
    )


TEXTO_SIN_PLAN = (
    "Su número aún no tiene un plan activo en eki.\n\n"
    "Pida a su organización que lo active. Si ya tiene un curso en marcha, "
    "escriba *curso* para seguirlo."
)

TEXTO_PLAN_SIN_ASESOR = (
    "Su plan no incluye el asesor.\n\n"
    "Puede seguir con sus cursos de formación. _*menu* para volver._"
)

TEXTO_PLAN_SIN_CURSOS = (
    "Su plan no incluye cursos nuevos.\n\n"
    "Puede usar el asesor. _*menu* para volver._"
)
