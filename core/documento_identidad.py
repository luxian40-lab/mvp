"""Reexport de fase H2. El código vive en core.analitica.documento_identidad."""
import core.analitica.documento_identidad as _impl
import sys as _sys
_sys.modules[__name__] = _impl
