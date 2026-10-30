"""Reexport de fase H2. El código vive en core.agentes.base_conocimientos."""
import core.agentes.base_conocimientos as _impl
import sys as _sys
_sys.modules[__name__] = _impl
