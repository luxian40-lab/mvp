"""Reexport de fase H2. El código vive en core.curso.modulo_publicacion."""
import core.curso.modulo_publicacion as _impl
import sys as _sys
_sys.modules[__name__] = _impl
