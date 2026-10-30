"""Reexport de fase H2. El código vive en core.canal.envios."""
import core.canal.envios as _impl
import sys as _sys
_sys.modules[__name__] = _impl
