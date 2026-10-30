"""Reexport de fase H2. El código vive en core.agentes.ia_empatica."""
import core.agentes.ia_empatica as _impl
import sys as _sys
_sys.modules[__name__] = _impl
