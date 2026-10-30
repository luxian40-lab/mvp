"""Reexport de fase H2. El código vive en core.agentes.ai_capabilities."""
import core.agentes.ai_capabilities as _impl
import sys as _sys
_sys.modules[__name__] = _impl
