"""Reexport de fase H2. El código vive en core.analitica.client_logos."""
import core.analitica.client_logos as _impl
import sys as _sys
_sys.modules[__name__] = _impl
