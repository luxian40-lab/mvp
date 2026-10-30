"""Reexport de fase H2. El código vive en core.conversacion.correccion_datos."""
import core.conversacion.correccion_datos as _impl
import sys as _sys
_sys.modules[__name__] = _impl
