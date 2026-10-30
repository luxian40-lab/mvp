"""Reexport de fase H2. El código vive en core.curso.media_encode_async."""
import core.curso.media_encode_async as _impl
import sys as _sys
_sys.modules[__name__] = _impl
