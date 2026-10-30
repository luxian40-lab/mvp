"""Reexport de fase H2. El código vive en core.analitica.sentry_eki."""
import core.analitica.sentry_eki as _impl
import sys as _sys
_sys.modules[__name__] = _impl
