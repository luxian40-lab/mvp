"""Reexport de fase H2. El código vive en core.canal.meta_waba."""
import core.canal.meta_waba as _impl
import sys as _sys
_sys.modules[__name__] = _impl
