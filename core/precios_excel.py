"""Reexport de fase H2. El código vive en core.campanas.precios_excel."""
import core.campanas.precios_excel as _impl
import sys as _sys
_sys.modules[__name__] = _impl
