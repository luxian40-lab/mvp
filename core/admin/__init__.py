"""
Registro admin de core (paquete partido desde el antiguo core/admin.py monolítico).

Importar submódulos registra los ModelAdmin en django.contrib.admin.
El orden importa: clases compartidas (inlines/forms) deben cargarse antes de usarlas.
"""
from ._common import (  # noqa: F401
    CursosEstudianteFilter,
    GruposEstudianteFilter,
    guardar_upload_admin_media,
)

# 1 — inlines y forms base
from .clientes import *  # noqa: F401,F403
from .plantillas import *  # noqa: F401,F403
from .estudiantes import *  # noqa: F401,F403  # EnvioProgramadoInline, EnvioProgramadoForm

# 2 — dependen de estudiantes
from .campanas import *  # noqa: F401,F403
from .cursos import *  # noqa: F401,F403
from .gamificacion import *  # noqa: F401,F403
from .soporte import *  # noqa: F401,F403
from .certificados import *  # noqa: F401,F403
from .audit import *  # noqa: F401,F403
from .grupos import *  # noqa: F401,F403
from .plantilla_dashboard import *  # noqa: F401,F403
from .commercial import *  # noqa: F401,F403
from .commercial import (  # re-export helpers usados por core.tasks
    _extension_archivo_comercial_ok,
    _nombre_documento_desde_nombre_archivo,
    _nombre_rag_comercial_unico,
)
from .sistema import *  # noqa: F401,F403
