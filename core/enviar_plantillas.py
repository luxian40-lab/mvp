"""Reexport de fase H2. El código vive en core.campanas.enviar_plantillas."""
import core.campanas.enviar_plantillas as _impl
import sys as _sys
_sys.modules[__name__] = _impl
