"""Reexport de fase H2. El código vive en core.curso.module_builder_lectura."""
import core.curso.module_builder_lectura as _impl
import sys as _sys
_sys.modules[__name__] = _impl
