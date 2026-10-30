"""Reexport de fase H2. El código vive en core.analitica.extractores_documento."""
import core.analitica.extractores_documento as _impl
import sys as _sys
_sys.modules[__name__] = _impl
