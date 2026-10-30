"""Reexport de fase H2. El código vive en core.campanas.mensajes_push."""
import core.campanas.mensajes_push as _impl
import sys as _sys
_sys.modules[__name__] = _impl
