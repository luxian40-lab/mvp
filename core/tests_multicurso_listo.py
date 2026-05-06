"""Regresión: continuar_leccion no debe saltar a otro curso tras reto si hay foco explícito."""

from datetime import timedelta

import pytest
from django.utils import timezone

from core.helpers_examenes import contexto_temporal_tras_cerrar_agente
from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from core.response_templates import get_response_for_intent

pytestmark = pytest.mark.django_db


def test_contexto_temporal_tras_cerrar_agente_conserva_curso_y_ts():
    class _ProgresoFake:
        curso_id = 99

    assert contexto_temporal_tras_cerrar_agente(_ProgresoFake(), None) == {"curso_activo_id": 99}
    assert contexto_temporal_tras_cerrar_agente(
        None, {"curso_activo_id": 7, "_ts_leccion": 1.2}
    ) == {"curso_activo_id": 7, "_ts_leccion": 1.2}
    assert contexto_temporal_tras_cerrar_agente(
        _ProgresoFake(), {"curso_activo_id": 7, "_ts_leccion": 3.0}
    ) == {"curso_activo_id": 99, "_ts_leccion": 3.0}
    assert contexto_temporal_tras_cerrar_agente(None, None) is None


def test_continuar_leccion_usa_curso_activo_con_dos_progresos():
    cliente = Cliente.objects.create(
        nombre="Org MC",
        contacto_principal="A",
        email="mc@t.co",
        telefono="573001111113",
    )
    est = Estudiante.objects.create(
        cedula="9102", nombre="JulianTest", telefono="57300991002", cliente=cliente
    )

    curso_a = Curso.objects.create(
        nombre="Curso A finanzas",
        descripcion="a",
        activo=True,
        cliente=cliente,
        dias_espera_entre_modulos=0,
    )
    curso_b = Curso.objects.create(
        nombre="Curso B otro",
        descripcion="b",
        activo=True,
        cliente=cliente,
        dias_espera_entre_modulos=0,
    )

    def _mods(curso, prefix: str):
        out = []
        for n in range(1, 6):
            out.append(
                Modulo.objects.create(
                    curso=curso,
                    numero=n,
                    titulo=f"{prefix}-M{n}",
                    descripcion="d",
                    contenido=f"c{n}",
                    duracion_dias=1,
                )
            )
        return out

    mods_a = _mods(curso_a, "A")
    _mods(curso_b, "B")

    older = timezone.now() - timedelta(days=30)
    newer = timezone.now()

    # B más reciente: sin curso_activo_id, .first() seguiría el curso B.
    mod2_b = curso_b.modulos.get(numero=2)
    ProgresoEstudiante.objects.create(
        estudiante=est,
        curso=curso_b,
        modulo_actual=mod2_b,
        completado=False,
        fecha_inicio=newer,
    )

    prog_a = ProgresoEstudiante.objects.create(
        estudiante=est,
        curso=curso_a,
        modulo_actual=mods_a[3],
        completado=False,
        fecha_inicio=older,
    )

    est.contexto_temporal = {
        "curso_activo_id": curso_a.id,
        "_ts_leccion": 0.0,
    }
    est.save(update_fields=["contexto_temporal"])

    resp = get_response_for_intent(
        "continuar_leccion",
        est.nombre,
        estudiante_id=est.id,
        mensaje_original="listo",
    )

    assert "A-M5" in resp, resp[:800]
    assert "B-M" not in resp
