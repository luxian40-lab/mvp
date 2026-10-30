"""Reexport de fase H2. El código vive en core.analitica.health_deep."""
import core.analitica.health_deep as _impl
import sys as _sys
_sys.modules[__name__] = _impl
