"""Reexport de fase H2. El código vive en core.analitica.alerta_territorial_ops."""
import core.analitica.alerta_territorial_ops as _impl
import sys as _sys
_sys.modules[__name__] = _impl
