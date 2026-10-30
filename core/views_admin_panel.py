"""Reexport de fase H2. El código vive en core.admin_vistas.views_admin_panel."""
import core.admin_vistas.views_admin_panel as _impl
import sys as _sys
_sys.modules[__name__] = _impl
