"""Reexport de fase H2. El código vive en core.canal.sandbox_canal."""
import core.canal.sandbox_canal as _impl
import sys as _sys
_sys.modules[__name__] = _impl
