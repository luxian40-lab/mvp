"""Reexport de fase H2. El código vive en core.curso.avance_reset_service."""
import core.curso.avance_reset_service as _impl
import sys as _sys
_sys.modules[__name__] = _impl
