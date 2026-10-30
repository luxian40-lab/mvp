"""Reexport de fase H2. El código vive en core.agentes.copiar_conocimiento_nati."""
import core.agentes.copiar_conocimiento_nati as _impl
import sys as _sys
_sys.modules[__name__] = _impl
