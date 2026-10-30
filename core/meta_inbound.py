"""Reexport de fase H2. El código vive en core.canal.meta_inbound."""
import core.canal.meta_inbound as _impl
import sys as _sys
_sys.modules[__name__] = _impl
