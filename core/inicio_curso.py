"""Reexport de fase H2. El código vive en core.curso.inicio_curso."""
import core.curso.inicio_curso as _impl
import sys as _sys
_sys.modules[__name__] = _impl
