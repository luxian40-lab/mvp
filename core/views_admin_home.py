"""Reexport de fase H2. El código vive en core.admin_vistas.views_admin_home."""
import core.admin_vistas.views_admin_home as _impl
import sys as _sys
_sys.modules[__name__] = _impl
