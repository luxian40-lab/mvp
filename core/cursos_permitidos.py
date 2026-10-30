"""Reexport de fase H2. El código vive en core.curso.cursos_permitidos."""
import core.curso.cursos_permitidos as _impl
import sys as _sys
_sys.modules[__name__] = _impl
