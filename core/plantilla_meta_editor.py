"""Reexport de fase H2. El código vive en core.campanas.plantilla_meta_editor."""
import core.campanas.plantilla_meta_editor as _impl
import sys as _sys
_sys.modules[__name__] = _impl
