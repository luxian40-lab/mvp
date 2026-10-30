"""Reexport de fase H2. El código vive en core.agentes.openai_compat."""
import core.agentes.openai_compat as _impl
import sys as _sys
_sys.modules[__name__] = _impl
