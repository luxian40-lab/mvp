"""Reexport de fase H2. El código vive en core.conversacion.security_handler."""
import core.conversacion.security_handler as _impl
import sys as _sys
_sys.modules[__name__] = _impl
