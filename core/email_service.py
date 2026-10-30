"""Reexport de fase H2. El código vive en core.analitica.email_service."""
import core.analitica.email_service as _impl
import sys as _sys
_sys.modules[__name__] = _impl
