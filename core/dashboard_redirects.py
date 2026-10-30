"""Reexport de fase H2. El código vive en core.analitica.dashboard_redirects."""
import core.analitica.dashboard_redirects as _impl
import sys as _sys
_sys.modules[__name__] = _impl
