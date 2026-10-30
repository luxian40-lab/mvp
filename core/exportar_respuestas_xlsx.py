"""Reexport de fase H2. El código vive en core.analitica.exportar_respuestas_xlsx."""
import core.analitica.exportar_respuestas_xlsx as _impl
import sys as _sys
_sys.modules[__name__] = _impl
