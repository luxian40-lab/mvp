"""Reexport de fase H2. El código vive en core.analitica.empleabilidad_pausa."""
import core.analitica.empleabilidad_pausa as _impl
import sys as _sys
_sys.modules[__name__] = _impl
