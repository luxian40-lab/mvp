"""Reexport de fase H2. El código vive en core.analitica.metricas_empresa."""
import core.analitica.metricas_empresa as _impl
import sys as _sys
_sys.modules[__name__] = _impl
