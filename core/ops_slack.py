"""Reexport de fase H2. El código vive en core.analitica.ops_slack."""
import core.analitica.ops_slack as _impl
import sys as _sys
_sys.modules[__name__] = _impl
