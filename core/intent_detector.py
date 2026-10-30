"""Reexport de fase H2. El código vive en core.conversacion.intent_detector."""
import core.conversacion.intent_detector as _impl
import sys as _sys
_sys.modules[__name__] = _impl
