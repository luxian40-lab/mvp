"""Reexport de fase H2. El código vive en core.analitica.import_estudiantes_excel."""
import core.analitica.import_estudiantes_excel as _impl
import sys as _sys
_sys.modules[__name__] = _impl
