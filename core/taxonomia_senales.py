"""Reexport de fase H2. El código vive en core.analitica.taxonomia_senales."""
import core.analitica.taxonomia_senales as _impl
import sys as _sys
_sys.modules[__name__] = _impl
