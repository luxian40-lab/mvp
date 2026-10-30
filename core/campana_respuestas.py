"""Reexport de fase H2. El código vive en core.campanas.campana_respuestas."""
import core.campanas.campana_respuestas as _impl
import sys as _sys
_sys.modules[__name__] = _impl
