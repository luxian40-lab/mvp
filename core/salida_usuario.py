"""Reexport de fase H2. El código vive en core.conversacion.salida_usuario."""
import core.conversacion.salida_usuario as _impl
import sys as _sys
_sys.modules[__name__] = _impl
