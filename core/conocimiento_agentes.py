"""Reexport de fase H2. El código vive en core.agentes.conocimiento_agentes."""
import core.agentes.conocimiento_agentes as _impl
import sys as _sys
_sys.modules[__name__] = _impl
