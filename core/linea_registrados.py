"""Reexport de fase H2. El código vive en core.canal.linea_registrados."""
import core.canal.linea_registrados as _impl
import sys as _sys
_sys.modules[__name__] = _impl
