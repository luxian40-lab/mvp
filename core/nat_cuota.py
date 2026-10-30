"""Reexport de fase H2. El código vive en core.agentes.nat_cuota."""
import core.agentes.nat_cuota as _impl
import sys as _sys
_sys.modules[__name__] = _impl
