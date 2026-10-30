"""Reexport de fase H2. El código vive en core.conversacion.avance_whatsapp."""
import core.conversacion.avance_whatsapp as _impl
import sys as _sys
_sys.modules[__name__] = _impl
