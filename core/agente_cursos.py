"""Reexport de fase H2. El código vive en core.agentes.agente_cursos."""
import core.agentes.agente_cursos as _impl
import sys as _sys
_sys.modules[__name__] = _impl
