"""Reexport de fase H2. El código vive en core.curso.cursos_generales."""
import core.curso.cursos_generales as _impl
import sys as _sys
_sys.modules[__name__] = _impl
