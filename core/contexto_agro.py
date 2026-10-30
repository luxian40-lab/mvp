"""Reexport de fase H2. El código vive en core.agentes.contexto_agro."""
import core.agentes.contexto_agro as _impl
import sys as _sys
_sys.modules[__name__] = _impl
