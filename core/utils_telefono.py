"""Reexport de fase H2. El código vive en core.canal.utils_telefono."""
import core.canal.utils_telefono as _impl
import sys as _sys
_sys.modules[__name__] = _impl
