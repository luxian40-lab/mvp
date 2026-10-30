"""Reexport de fase H2. El código vive en core.admin_vistas.views_infra_admin."""
import core.admin_vistas.views_infra_admin as _impl
import sys as _sys
_sys.modules[__name__] = _impl
