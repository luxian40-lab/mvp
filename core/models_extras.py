"""Reexport de fase H2. El código vive en core.analitica.models_extras."""
import core.analitica.models_extras as _impl
import sys as _sys
_sys.modules[__name__] = _impl
