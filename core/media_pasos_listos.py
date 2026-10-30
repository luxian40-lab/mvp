"""Reexport de fase H2. El código vive en core.curso.media_pasos_listos."""
import core.curso.media_pasos_listos as _impl
import sys as _sys
_sys.modules[__name__] = _impl
