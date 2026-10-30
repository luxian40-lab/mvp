"""Reexport de fase H2. El código vive en core.analitica.models_notas."""
import core.analitica.models_notas as _impl
import sys as _sys
_sys.modules[__name__] = _impl
