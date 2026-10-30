"""Reexport de fase H2. El código vive en core.campanas.precios_import."""
import core.campanas.precios_import as _impl
import sys as _sys
_sys.modules[__name__] = _impl
