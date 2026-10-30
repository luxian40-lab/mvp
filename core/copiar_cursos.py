"""Reexport de fase H2. El código vive en core.curso.copiar_cursos."""
import core.curso.copiar_cursos as _impl
import sys as _sys
_sys.modules[__name__] = _impl
