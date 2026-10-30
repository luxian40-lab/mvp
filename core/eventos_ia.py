"""Reexport de fase H2. El código vive en core.agentes.eventos_ia."""
import core.agentes.eventos_ia as _impl
import sys as _sys
_sys.modules[__name__] = _impl
