"""Reexport de fase H2. El código vive en core.conversacion.seguimiento_proactivo."""
import core.conversacion.seguimiento_proactivo as _impl
import sys as _sys
_sys.modules[__name__] = _impl
