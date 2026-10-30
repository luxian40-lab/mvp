"""Reexport de fase H2. El código vive en core.curso.grupos_miembros."""
import core.curso.grupos_miembros as _impl
import sys as _sys
_sys.modules[__name__] = _impl
