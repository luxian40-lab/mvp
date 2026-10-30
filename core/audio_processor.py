"""Reexport de fase H2. El código vive en core.agentes.audio_processor."""
import core.agentes.audio_processor as _impl
import sys as _sys
_sys.modules[__name__] = _impl
