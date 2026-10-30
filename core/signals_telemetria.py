"""Reexport de fase H2. El código vive en core.analitica.signals_telemetria."""
import core.analitica.signals_telemetria as _impl
import sys as _sys
_sys.modules[__name__] = _impl
