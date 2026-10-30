"""Reexport de fase H2. El código vive en core.analitica.copiloto_ops."""
import core.analitica.copiloto_ops as _impl
import sys as _sys
_sys.modules[__name__] = _impl
