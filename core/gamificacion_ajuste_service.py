"""Reexport de fase H2. El código vive en core.gamificacion.ajuste_service."""
import core.gamificacion.ajuste_service as _impl
import sys as _sys
_sys.modules[__name__] = _impl
