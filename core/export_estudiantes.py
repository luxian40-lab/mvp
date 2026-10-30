"""Reexport de fase H2. El código vive en core.analitica.export_estudiantes."""
import core.analitica.export_estudiantes as _impl
import sys as _sys
_sys.modules[__name__] = _impl
