"""Reexport de fase H2. El código vive en core.agentes.pqrs_acciones."""
import core.agentes.pqrs_acciones as _impl
import sys as _sys
_sys.modules[__name__] = _impl
