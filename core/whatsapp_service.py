"""Reexport de fase H2. El código vive en core.canal.whatsapp_service."""
import core.canal.whatsapp_service as _impl
import sys as _sys
_sys.modules[__name__] = _impl
