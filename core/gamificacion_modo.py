"""Reexport de fase H2. El código vive en core.gamificacion.modo."""
import core.gamificacion.modo as _impl
import sys as _sys
_sys.modules[__name__] = _impl
