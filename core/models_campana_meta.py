"""Reexport de fase H2. El código vive en core.campanas.models_campana_meta."""
import core.campanas.models_campana_meta as _impl
import sys as _sys
_sys.modules[__name__] = _impl
