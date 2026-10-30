"""Reexport de fase H2. El código vive en core.conversacion.rate_limit."""
import core.conversacion.rate_limit as _impl
import sys as _sys
_sys.modules[__name__] = _impl
