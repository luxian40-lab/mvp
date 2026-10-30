"""Reexport de fase H2. El código vive en core.agentes.biblioteca_nat_service."""
import core.agentes.biblioteca_nat_service as _impl
import sys as _sys
_sys.modules[__name__] = _impl
