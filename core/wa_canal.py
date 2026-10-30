"""Reexport de fase H2. El código vive en core.canal.wa_canal."""
import core.canal.wa_canal as _impl
import sys as _sys
_sys.modules[__name__] = _impl
