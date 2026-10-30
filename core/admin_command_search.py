"""Reexport de fase H2. El código vive en core.admin_vistas.admin_command_search."""
import core.admin_vistas.admin_command_search as _impl
import sys as _sys
_sys.modules[__name__] = _impl
