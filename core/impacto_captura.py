"""Reexport de fase H2. El código vive en core.analitica.impacto_captura."""
import core.analitica.impacto_captura as _impl
import sys as _sys
_sys.modules[__name__] = _impl
