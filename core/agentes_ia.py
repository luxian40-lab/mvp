"""Reexport de fase H2. El código vive en core.agentes.agentes_ia."""
import core.agentes.agentes_ia as _impl
import sys as _sys
_sys.modules[__name__] = _impl
