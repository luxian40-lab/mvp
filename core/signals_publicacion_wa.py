"""Reexport de fase H2. El código vive en core.curso.signals_publicacion_wa."""
import core.curso.signals_publicacion_wa as _impl
import sys as _sys
_sys.modules[__name__] = _impl
