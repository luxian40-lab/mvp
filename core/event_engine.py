"""Reexport de fase H2. El código vive en core.agentes.event_engine."""
import core.agentes.event_engine as _impl
import sys as _sys
_sys.modules[__name__] = _impl
