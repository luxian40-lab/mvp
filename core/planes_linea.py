"""Reexport de fase H2. El código vive en core.canal.planes_linea."""
import core.canal.planes_linea as _impl
import sys as _sys
_sys.modules[__name__] = _impl
