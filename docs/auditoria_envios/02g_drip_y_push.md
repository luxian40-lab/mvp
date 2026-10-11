# 02g — Drip, ventana y mensajes push

Volcado literal para auditoría. Teléfonos y Content SID (HX…) del fuente aparecen como `[REDACTADO]`. No se recortó lógica.

### `drip_schedule` — `core/drip_schedule.py:1`

```python
# core/drip_schedule.py:1
"""
Ritmo drip entre módulos: días de espera (curso + override por cliente)
y calendario por módulo (global en Modulo o por cliente en HabilitacionModuloDripCliente).
"""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.utils import timezone

if TYPE_CHECKING:
    from .models import Curso, Estudiante, Modulo, ProgresoEstudiante


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `dias_espera_efectivos` — `core/drip_schedule.py:16`

```python
# core/drip_schedule.py:16
def dias_espera_efectivos(estudiante: Estudiante | None, curso: Curso | None) -> int:
    """
    Días de espera obligatorios entre módulos para este par estudiante-curso.
    Sin estudiante o sin cliente: solo aplica la configuración del curso.
    """
    if curso is None:
        return 0
    base = max(0, int(curso.dias_espera_entre_modulos or 0))
    if estudiante is None or not getattr(estudiante, 'cliente_id', None):
        return base
    from .models import ConfiguracionDripCliente

    cfg = (
        ConfiguracionDripCliente.objects.filter(
            cliente_id=estudiante.cliente_id,
            curso_id=curso.id,
            activo=True,
        )
        .only('dias_espera_entre_modulos')
        .first()
    )
    if cfg is None or cfg.dias_espera_entre_modulos is None:
        return base
    return max(0, int(cfg.dias_espera_entre_modulos))


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `fecha_desbloqueo_drip` — `core/drip_schedule.py:42`

```python
# core/drip_schedule.py:42
def fecha_desbloqueo_drip(fecha_ultimo_avance, dias_espera: int):
    """
    Fecha calendario en que se desbloquea el siguiente módulo.
    Regla de negocio: el desbloqueo es por día (no por hora exacta).
    """
    if not fecha_ultimo_avance or dias_espera <= 0:
        return None
    return timezone.localdate(fecha_ultimo_avance) + timedelta(days=dias_espera)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_siguiente_modulo_orden` — `core/drip_schedule.py:52`

```python
# core/drip_schedule.py:52
def _siguiente_modulo_orden(curso, modulo_actual) -> Modulo | None:
    if modulo_actual is None or curso is None:
        return None
    from .modulo_publicacion import siguiente_modulo_publicado_wa

    return siguiente_modulo_publicado_wa(curso, modulo_actual)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `estudiante_autorizado_en_modulo` — `core/drip_schedule.py:60`

```python
# core/drip_schedule.py:60
def estudiante_autorizado_en_modulo(estudiante: Estudiante | None, modulo: Modulo | None) -> bool:
    """
    Con «Módulos solo por lista» en el cliente, el estudiante debe tener fila activa.
    Si no está activada esa política, todos los estudiantes del cliente pueden intentar el módulo
    (sujeto al calendario/drip).
    """
    if modulo is None or estudiante is None:
        return True
    cliente = getattr(estudiante, 'cliente', None)
    if not cliente or not getattr(cliente, 'drip_modulos_solo_estudiantes_listados', False):
        return True
    from .models import HabilitacionModuloEstudiante

    return HabilitacionModuloEstudiante.objects.filter(
        estudiante_id=estudiante.id,
        curso_id=modulo.curso_id,
        modulo_id=modulo.id,
        activo=True,
    ).exists()


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `habilitado_desde_efectivo` — `core/drip_schedule.py:81`

```python
# core/drip_schedule.py:81
def habilitado_desde_efectivo(estudiante: Estudiante | None, modulo: Modulo | None):
    """
    datetime a partir del cual el módulo puede enviarse, o None = sin restricción de calendario.
    Prioridad: estudiante → cliente × curso × módulo → Modulo.habilitado_desde.
    """
    if modulo is None:
        return None
    curso_id = modulo.curso_id
    if estudiante is not None:
        from .models import HabilitacionModuloEstudiante, HabilitacionModuloDripCliente

        row_est = (
            HabilitacionModuloEstudiante.objects.filter(
                estudiante_id=estudiante.id,
                curso_id=curso_id,
                modulo_id=modulo.id,
                activo=True,
            )
            .only('habilitado_desde')
            .first()
        )
        if row_est is not None and row_est.habilitado_desde:
            return row_est.habilitado_desde

        if getattr(estudiante, 'cliente_id', None):
            row = (
                HabilitacionModuloDripCliente.objects.filter(
                    cliente_id=estudiante.cliente_id,
                    curso_id=curso_id,
                    modulo_id=modulo.id,
                    activo=True,
                )
                .only('habilitado_desde')
                .first()
            )
            if row is not None and row.habilitado_desde:
                return row.habilitado_desde
    return getattr(modulo, 'habilitado_desde', None) or None


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `calendario_bloquea_modulo` — `core/drip_schedule.py:121`

```python
# core/drip_schedule.py:121
def calendario_bloquea_modulo(estudiante: Estudiante | None, modulo: Modulo | None) -> bool:
    """True si aún no se cumple la fecha/hora de habilitación del módulo."""
    dt = habilitado_desde_efectivo(estudiante, modulo)
    if not dt:
        return False
    return timezone.now() < dt


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `format_mensaje_bloqueo_drip` — `core/drip_schedule.py:129`

```python
# core/drip_schedule.py:129
def format_mensaje_bloqueo_drip(fecha_desbloqueo, cliente=None) -> str:
    """Mensaje WhatsApp: espera por días entre módulos (mismo tono que el drip histórico)."""
    from .avance_whatsapp import texto_bloqueo_drip_cierre

    if hasattr(fecha_desbloqueo, 'hour'):
        f_txt = timezone.localtime(fecha_desbloqueo).strftime('%d/%m/%Y')
    else:
        f_txt = fecha_desbloqueo.strftime('%d/%m/%Y')
    return (
        '*¡Excelente energía!*\n\n'
        'Estamos preparando tu siguiente sesión; aún no enviamos el siguiente módulo para que puedas asimilar lo aprendido.\n\n'
        f'Tu próxima lección se desbloquea el *{f_txt}*.\n'
        'Mientras tanto, repasa el material del módulo que acabas de completar.\n\n'
        f'{texto_bloqueo_drip_cierre(cliente)}'
    )


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `format_mensaje_bloqueo_calendario_modulo` — `core/drip_schedule.py:146`

```python
# core/drip_schedule.py:146
def format_mensaje_bloqueo_calendario_modulo(habilitado_desde, cliente=None) -> str:
    """Mismo tono que el drip por días; la fecha incluye hora (calendario programado)."""
    from .avance_whatsapp import texto_bloqueo_drip_cierre

    f_txt = timezone.localtime(habilitado_desde).strftime('%d/%m/%Y a las %H:%M')
    return (
        '*¡Excelente energía!*\n\n'
        'Estamos preparando tu siguiente sesión; aún no enviamos el siguiente módulo para que puedas asimilar lo aprendido.\n\n'
        f'Tu próxima lección se desbloquea el *{f_txt}*.\n'
        'Mientras tanto, repasa el material del módulo que acabas de completar.\n\n'
        f'{texto_bloqueo_drip_cierre(cliente)}'
    )


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `mensaje_bloqueo_avance_siguiente_modulo` — `core/drip_schedule.py:160`

```python
# core/drip_schedule.py:160
def mensaje_bloqueo_avance_siguiente_modulo(
    estudiante: Estudiante | None,
    progreso: ProgresoEstudiante,
    modulo_actual,
) -> str | None:
    """
    None = puede abrir el siguiente módulo (respecto a drip por días + calendario).
    Si aplica bloqueo, devuelve uno o dos párrafos (drip y/o calendario).
    Requiere que el módulo actual esté marcado como completado en ModuloCompletado.
    """
    from .models import ModuloCompletado

    if modulo_actual is None or progreso is None or progreso.curso_id is None:
        return None
    siguiente = _siguiente_modulo_orden(progreso.curso, modulo_actual)
    if siguiente is None:
        return None
    if not ModuloCompletado.objects.filter(
        progreso=progreso, modulo=modulo_actual
    ).exists():
        return None

    cliente = getattr(estudiante, 'cliente', None) if estudiante else None
    partes: list[str] = []
    d = dias_espera_efectivos(estudiante, progreso.curso)
    if d > 0 and progreso.fecha_ultimo_avance:
        fecha_desbloqueo = fecha_desbloqueo_drip(progreso.fecha_ultimo_avance, d)
        if fecha_desbloqueo and timezone.localdate() < fecha_desbloqueo:
            partes.append(format_mensaje_bloqueo_drip(fecha_desbloqueo, cliente))

    cal_dt = habilitado_desde_efectivo(estudiante, siguiente)
    if cal_dt and timezone.now() < cal_dt:
        partes.append(format_mensaje_bloqueo_calendario_modulo(cal_dt, cliente))

    if not partes:
        return None
    return '\n\n'.join(partes)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `modulos_curso_ordenados` — `core/drip_schedule.py:199`

```python
# core/drip_schedule.py:199
def modulos_curso_ordenados(curso: Curso | None) -> list:
    """Módulos del curso ordenados por número."""
    if curso is None:
        return []
    return list(curso.modulos.order_by('numero'))


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `modulo_disponible_por_calendario` — `core/drip_schedule.py:206`

```python
# core/drip_schedule.py:206
def modulo_disponible_por_calendario(
    estudiante: Estudiante | None,
    modulo: Modulo | None,
    referencia=None,
) -> bool:
    """True si el estudiante puede acceder al módulo (lista, calendario drip)."""
    if modulo is None:
        return False
    if not estudiante_autorizado_en_modulo(estudiante, modulo):
        return False
    dt = habilitado_desde_efectivo(estudiante, modulo)
    if not dt:
        return True
    now = referencia or timezone.now()
    return now >= dt


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `modulos_para_metricas` — `core/drip_schedule.py:223`

```python
# core/drip_schedule.py:223
def modulos_para_metricas(
    estudiante: Estudiante | None,
    curso: Curso | None,
    *,
    modulo_hasta_numero: int | None = None,
    usar_drip_calendario: bool = True,
    referencia=None,
) -> list:
    """
    Módulos que cuentan como «disponibles» para calcular avance en dashboards.
    - modulo_hasta_numero: solo M1..MN (simula drip liberado hasta esa semana).
    - usar_drip_calendario: excluye módulos cuya habilitado_desde aún no llega.
    - Solo módulos publicados WA (cursos modo clases: todos).
    """
    from .modulo_publicacion import modulos_publicados_wa

    mods = modulos_publicados_wa(curso)
    if modulo_hasta_numero is not None:
        mods = [m for m in mods if m.numero <= modulo_hasta_numero]
    if usar_drip_calendario:
        mods = [
            m for m in mods
            if modulo_disponible_por_calendario(estudiante, m, referencia=referencia)
        ]
    return mods


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `avance_sobre_modulos` — `core/drip_schedule.py:250`

```python
# core/drip_schedule.py:250
def avance_sobre_modulos(progreso: ProgresoEstudiante, modulos_disponibles: list) -> tuple[int, int, int]:
    """(completados, total_disponibles, porcentaje 0-100) dentro del subconjunto drip."""
    from .models import ModuloCompletado

    total = len(modulos_disponibles)
    if not total:
        return 0, 0, 0
    ids = {m.id for m in modulos_disponibles}
    comps = ModuloCompletado.objects.filter(
        progreso=progreso, modulo_id__in=ids
    ).count()
    return comps, total, round(comps / total * 100)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `max_modulo_alcanzado` — `core/drip_schedule.py:264`

```python
# core/drip_schedule.py:264
def max_modulo_alcanzado(progreso: ProgresoEstudiante) -> int:
    """Mayor número de módulo completado o módulo actual (1-based)."""
    from django.db.models import Max
    from .models import ModuloCompletado

    if not progreso:
        return 0
    if progreso.completado and progreso.curso_id:
        ultimo = progreso.curso.modulos.order_by('-numero').values_list('numero', flat=True).first()
        return int(ultimo or 0)
    max_comp = ModuloCompletado.objects.filter(progreso=progreso).aggregate(
        m=Max('modulo__numero'),
    )['m'] or 0
    actual = progreso.modulo_actual.numero if progreso.modulo_actual_id else 0
    return max(int(max_comp), int(actual or 0))


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `estudiante_llego_hasta_modulo` — `core/drip_schedule.py:281`

```python
# core/drip_schedule.py:281
def estudiante_llego_hasta_modulo(progreso: ProgresoEstudiante, modulo_numero: int) -> bool:
    """True si el estudiante alcanzó al menos el módulo N (completó o está en él o más adelante)."""
    if not modulo_numero:
        return True
    return max_modulo_alcanzado(progreso) >= int(modulo_numero)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `drip_bloquea_siguiente_modulo` — `core/drip_schedule.py:288`

```python
# core/drip_schedule.py:288
def drip_bloquea_siguiente_modulo(progreso: ProgresoEstudiante, modulo_actual) -> bool:
    """
    True si el módulo actual ya quedó completado pero aún no se puede abrir el siguiente:
    por días de espera y/o por fecha programada del siguiente módulo.
    """
    return bool(
        mensaje_bloqueo_avance_siguiente_modulo(
            progreso.estudiante if progreso else None,
            progreso,
            modulo_actual,
        )
    )
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `ventana_drip` — `core/views/ventana_drip.py:1`

```python
# core/views/ventana_drip.py:1
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_cliente_en_ventana` — `core/views/ventana_drip.py:7`

```python
# core/views/ventana_drip.py:7
def _cliente_en_ventana(cliente, campo_habilitar, campo_inicio, campo_fin):
    """Evalúa si una funcionalidad está habilitada para un cliente según ventana de fechas."""
    if not cliente:
        return True
    if not getattr(cliente, campo_habilitar, False):
        return False

    hoy = timezone.localdate()
    inicio = getattr(cliente, campo_inicio, None)
    fin = getattr(cliente, campo_fin, None)

    if inicio and hoy < inicio:
        return False
    if fin and hoy > fin:
        return False
    return True

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_cliente_habilita_pregunta_abierta_final` — `core/views/ventana_drip.py:24`

```python
# core/views/ventana_drip.py:24
def _cliente_habilita_pregunta_abierta_final(cliente):
    return _cliente_en_ventana(
        cliente,
        'habilitar_pregunta_abierta_final',
        'fecha_inicio_pregunta_abierta_final',
        'fecha_fin_pregunta_abierta_final',
    )

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_mensaje_bloqueo_drip_view` — `core/views/ventana_drip.py:32`

```python
# core/views/ventana_drip.py:32
def _mensaje_bloqueo_drip_view(fecha_desbloqueo):
    from ..response_templates import _mensaje_bloqueo_drip
    return _mensaje_bloqueo_drip(fecha_desbloqueo)

```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `_pregunta_abierta_final_pendiente` — `core/views/ventana_drip.py:36`

```python
# core/views/ventana_drip.py:36
def _pregunta_abierta_final_pendiente(estudiante, progreso):
    from ..models import PreguntaAbiertaFinalCurso, RespuestaAbiertaFinal

    preguntas_qs = PreguntaAbiertaFinalCurso.objects.filter(
        curso=progreso.curso,
        activa=True
    ).order_by('orden', 'id')

    if not preguntas_qs.exists():
        return None

    cliente_habilita = _cliente_habilita_pregunta_abierta_final(estudiante.cliente)
    curso_habilita = bool(getattr(progreso.curso, 'habilitar_pregunta_abierta_final', False))
    if not (cliente_habilita and curso_habilita):
        logger.info(
            "⚠️ Fallback pregunta abierta final por configuración | estudiante_id=%s | curso_id=%s | cliente_habilita=%s | curso_habilita=%s",
            estudiante.id,
            progreso.curso.id,
            cliente_habilita,
            curso_habilita,
        )

    preguntas = list(preguntas_qs[:3])

    for pregunta in preguntas:
        existe = RespuestaAbiertaFinal.objects.filter(
            pregunta=pregunta,
            estudiante=estudiante
        ).exists()
        if not existe:
            return pregunta

    return None
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `mensajes_push` — `core/mensajes_push.py:1`

```python
# core/mensajes_push.py:1
"""Envío de mensajes push (recordatorios curso vía Twilio)."""
from __future__ import annotations

import logging

from django.db.models import Count, Q

from core.models import Estudiante, ProgresoEstudiante
from core.models_extras import EnvioMensajePush, GrupoEstudiantes, MensajePush

logger = logging.getLogger(__name__)


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `resolver_audiencia` — `core/mensajes_push.py:14`

```python
# core/mensajes_push.py:14
def resolver_audiencia(mensaje: MensajePush, grupo: GrupoEstudiantes | None = None):
    """Estudiantes destino según cliente, curso, tipo y grupo opcional."""
    qs = Estudiante.objects.filter(activo=True)
    if mensaje.cliente_id:
        qs = qs.filter(cliente_id=mensaje.cliente_id)
    if grupo:
        qs = qs.filter(grupos=grupo)
    if mensaje.tipo == 'recordatorio_inscripcion' and mensaje.curso_id:
        qs = qs.filter(progresos__curso_id=mensaje.curso_id, progresos__completado=False)
        qs = qs.annotate(
            n_mods=Count('progresos__modulos_completados', filter=Q(progresos__curso_id=mensaje.curso_id)),
        ).filter(n_mods=0)
    elif mensaje.curso_id:
        qs = qs.filter(progresos__curso_id=mensaje.curso_id, progresos__completado=False).distinct()
    return qs.select_related('cliente')


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_mensaje_push_a_estudiante` — `core/mensajes_push.py:31`

```python
# core/mensajes_push.py:31
def enviar_mensaje_push_a_estudiante(mensaje: MensajePush, estudiante: Estudiante) -> dict:
    """Envía un push; no altera onboarding ni reinicia curso."""
    from core.enviar_plantillas import enviar_plantilla_twilio
    from core.utils import enviar_whatsapp_twilio

    if not estudiante.telefono:
        return {'success': False, 'error': 'Sin teléfono'}

    progreso = None
    curso = mensaje.curso
    if curso:
        progreso = ProgresoEstudiante.objects.filter(estudiante=estudiante, curso=curso).first()
    texto = mensaje.render_texto(estudiante, curso=curso)
    sid = (mensaje.twilio_content_sid or '').strip()
    if not sid and mensaje.plantilla_id:
        sid = (getattr(mensaje.plantilla, 'twilio_template_sid', None) or '').strip()

    if sid:
        resultado = enviar_plantilla_twilio(
            estudiante.telefono,
            sid,
            variables={'1': estudiante.nombre or 'estudiante', '2': curso.nombre if curso else 'curso'},
        )
    else:
        resultado = enviar_whatsapp_twilio(estudiante.telefono, texto)

    EnvioMensajePush.objects.create(
        mensaje_push=mensaje,
        estudiante=estudiante,
        telefono=estudiante.telefono,
        exito=bool(resultado.get('success')),
        detalle=(resultado.get('error') or resultado.get('mensaje_id') or '')[:255],
    )
    if resultado.get('success') and progreso:
        ctx = estudiante.contexto_temporal or {}
        ctx['ultimo_push_curso_id'] = progreso.curso_id
        estudiante.contexto_temporal = ctx
        estudiante.save(update_fields=['contexto_temporal'])
    return resultado


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_mensaje_push_masivo` — `core/mensajes_push.py:72`

```python
# core/mensajes_push.py:72
def enviar_mensaje_push_masivo(mensaje: MensajePush, grupo=None) -> dict:
    enviados = errores = 0
    for est in resolver_audiencia(mensaje, grupo=grupo):
        r = enviar_mensaje_push_a_estudiante(mensaje, est)
        if r.get('success'):
            enviados += 1
        else:
            errores += 1
    logger.info('[Push] %s: enviados=%s errores=%s', mensaje.nombre, enviados, errores)
    return {'enviados': enviados, 'errores': errores}


```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `enviar_push_a_estudiantes` — `core/mensajes_push.py:84`

```python
# core/mensajes_push.py:84
def enviar_push_a_estudiantes(mensaje: MensajePush, estudiante_ids: set[int] | list[int]) -> dict:
    """Envía un mensaje push solo a los estudiantes marcados (no altera el avance del curso)."""
    enviados = errores = 0
    qs = Estudiante.objects.filter(pk__in=estudiante_ids, activo=True)
    if mensaje.cliente_id:
        qs = qs.filter(cliente_id=mensaje.cliente_id)
    for est in qs.select_related('cliente'):
        r = enviar_mensaje_push_a_estudiante(mensaje, est)
        if r.get('success'):
            enviados += 1
        else:
            errores += 1
    logger.info('[Push] %s selección: enviados=%s errores=%s', mensaje.nombre, enviados, errores)
    return {'enviados': enviados, 'errores': errores}
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.


### `anti_duplicado_listo` — `core/response_templates.py:1249`

```python
# core/response_templates.py:1249
        # ═══════════════════════════════════════════════════════════════
        # ANTI-DUPLICADO v1.9.1: Prevenir que dos workers entreguen
        # el mismo módulo simultáneamente (race condition con Gunicorn).
        # Bypass: llamadas internas post-evaluación de microcontenidos
        # (_bypass_anti_duplicado) — el alumno acaba de responder A/B, no es doble *listo*.
        # ═══════════════════════════════════════════════════════════════
        import time as _time
        from django.db import transaction

        _dedup_ok = bool(kwargs.get('_bypass_anti_duplicado'))
        if not _dedup_ok:
            # Un segundo *listo* en el mismo hilo de un test suelta el turno anterior.
            # En el webhook la retención sigue activa y el segundo *listo* no avanza.
            previo = _turno_estudiante.get()
            if previo and previo != estudiante_id and not _retener_turno.get():
                soltar_turno_entrega_actual()
            try:
                with transaction.atomic():
                    est_lock = Estudiante.objects.select_for_update().get(id=estudiante_id)
                    ctx_lock = dict(est_lock.contexto_temporal or {})
                    now_ts = _time.time()
                    en_curso = (
                        ctx_lock.get('_leccion_enviando')
                        and now_ts - float(ctx_lock.get('_ts_leccion') or 0) < _VENTANA_ENTREGA_SEG
                    )
                    if en_curso:
                        print(
                            "⏳ [ANTI-DUPLICADO] continuar_leccion en curso: "
                            "el *listo* anterior todavía se está enviando",
                            flush=True,
                        )
                    else:
                        ctx_lock['_leccion_enviando'] = True
                        ctx_lock['_ts_leccion'] = now_ts
                        est_lock.contexto_temporal = ctx_lock
                        est_lock.save(update_fields=['contexto_temporal'])
                        _turno_estudiante.set(estudiante_id)
                        _dedup_ok = True
            except Exception as e:
                print(f"⚠️ [ANTI-DUPLICADO] Error en lock: {e}", flush=True)
                _dedup_ok = True  # En caso de error, permitir (fail-open)

        if not _dedup_ok:
            return LECCION_EN_CURSO
        # ═══════════════════════════════════════════════════════════════

        estudiante = Estudiante.objects.get(id=estudiante_id)

        try:
            from core.models import EstudianteEventoAprendizaje
            from core.telemetria import marcar_recordatorio_respondido, registrar_evento

            prog0 = (
                ProgresoEstudiante.objects.filter(estudiante=estudiante, completado=False)
                .select_related('curso', 'modulo_actual')
                .first()
            )
            registrar_evento(
                tipo=EstudianteEventoAprendizaje.TIPO_LISTO_RECIBIDO,
                estudiante=estudiante,
                curso=prog0.curso if prog0 else None,
                modulo=prog0.modulo_actual if prog0 else None,
                paso=getattr(prog0, 'paso_evaluacion_paso', None) if prog0 else None,
                metadata={'origen': 'continuar_leccion'},
            )
            marcar_recordatorio_respondido(estudiante)
        except Exception:
            pass
        
        mensaje_original = kwargs.get('mensaje_original', '').lower()
        
        # Validar que el estudiante existe
```

**Contrato**
- Entradas: parámetros de la firma (primera línea `def` del bloque).
- Salidas: los `return` que aparecen en el bloque.
- Efectos secundarios: escrituras ORM (`create`/`save`/`update`), HTTP (`requests`, `messages.create`) y logs (`logger`/`print`) presentes en el bloque.
- Excepciones: las capturadas por los `except` del bloque. Lo demás se propaga al caller.

