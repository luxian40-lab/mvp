"""Reexport de fase H2. El código vive en core.analitica.senal_shadow."""
import core.analitica.senal_shadow as _impl
import sys as _sys
_sys.modules[__name__] = _impl
