"""Reexport de fase H2. El código vive en core.analitica.host_isolation."""
import core.analitica.host_isolation as _impl
import sys as _sys
_sys.modules[__name__] = _impl
