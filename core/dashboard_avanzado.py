"""Reexport de fase H2. El código vive en core.analitica.dashboard_avanzado."""
import core.analitica.dashboard_avanzado as _impl
import sys as _sys
_sys.modules[__name__] = _impl
