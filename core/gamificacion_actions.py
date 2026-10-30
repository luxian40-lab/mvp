"""Reexport de fase H2. El código vive en core.gamificacion.actions."""
import core.gamificacion.actions as _impl
import sys as _sys
_sys.modules[__name__] = _impl
