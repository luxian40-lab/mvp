"""Reexport de fase H2. El código vive en core.gamificacion.signals."""
import core.gamificacion.signals as _impl
import sys as _sys
_sys.modules[__name__] = _impl
