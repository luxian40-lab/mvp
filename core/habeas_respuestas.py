"""Reexport de fase H2. El código vive en core.conversacion.habeas_respuestas."""
import core.conversacion.habeas_respuestas as _impl
import sys as _sys
_sys.modules[__name__] = _impl
