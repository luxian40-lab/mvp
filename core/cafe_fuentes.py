"""Reexport de fase H2. El código vive en core.agentes.cafe_fuentes."""
import core.agentes.cafe_fuentes as _impl
import sys as _sys
_sys.modules[__name__] = _impl
