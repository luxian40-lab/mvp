"""Reexport de fase H2. El código vive en core.agentes.sandbox_agentes."""
import core.agentes.sandbox_agentes as _impl
import sys as _sys
_sys.modules[__name__] = _impl
