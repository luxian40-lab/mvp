"""Reexport de fase H2. El código vive en core.agentes.nati."""
import core.agentes.nati as _impl
import sys as _sys
_sys.modules[__name__] = _impl
