"""Reexport de fase H2. El código vive en core.conversacion.reto_evidencia."""
import core.conversacion.reto_evidencia as _impl
import sys as _sys
_sys.modules[__name__] = _impl
