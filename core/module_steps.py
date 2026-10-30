"""Reexport de fase H2. El código vive en core.curso.module_steps."""
import core.curso.module_steps as _impl
import sys as _sys
_sys.modules[__name__] = _impl
