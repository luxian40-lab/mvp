"""Reexport de fase H2. El código vive en core.analitica.excel_celdas."""
import core.analitica.excel_celdas as _impl
import sys as _sys
_sys.modules[__name__] = _impl
