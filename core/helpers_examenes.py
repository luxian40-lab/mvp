"""Reexport de fase H2. El código vive en core.curso.helpers_examenes."""
import core.curso.helpers_examenes as _impl
import sys as _sys
_sys.modules[__name__] = _impl
