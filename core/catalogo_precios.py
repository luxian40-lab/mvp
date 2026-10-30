"""Reexport de fase H2. El código vive en core.campanas.catalogo_precios."""
import core.campanas.catalogo_precios as _impl
import sys as _sys
_sys.modules[__name__] = _impl
