"""Reexport de fase H2. El código vive en core.analitica.services."""
import core.analitica.services as _impl
import sys as _sys
_sys.modules[__name__] = _impl
