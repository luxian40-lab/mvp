"""Registra en core lo que antes core importaba de esta app. Fase H3."""
from core.puentes import registrar

from studio.models import CuentaAula as _CuentaAula
registrar('CuentaAula', _CuentaAula)
from studio.models import OrdenStudio as _OrdenStudio
registrar('OrdenStudio', _OrdenStudio)
