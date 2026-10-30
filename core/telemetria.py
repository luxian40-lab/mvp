"""Reexport de fase H2. El código vive en core.analitica.telemetria."""
import core.analitica.telemetria as _impl
import sys as _sys
_sys.modules[__name__] = _impl
