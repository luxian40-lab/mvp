"""Reexport de fase H2. El código vive en core.curso.drip_schedule."""
import core.curso.drip_schedule as _impl
import sys as _sys
_sys.modules[__name__] = _impl
