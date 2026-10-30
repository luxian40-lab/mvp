"""Reexport de fase H2. El código vive en core.canal.twilio_timeout."""
import core.canal.twilio_timeout as _impl
import sys as _sys
_sys.modules[__name__] = _impl
