"""Reexport de fase H2. El código vive en core.canal.webhook_evento."""
import core.canal.webhook_evento as _impl
import sys as _sys
_sys.modules[__name__] = _impl
