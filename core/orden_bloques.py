"""Reexport de fase H2. El código vive en core.curso.orden_bloques."""
import core.curso.orden_bloques as _impl
import sys as _sys
_sys.modules[__name__] = _impl
