"""Reexport de fase H2. El código vive en core.curso.video_links."""
import core.curso.video_links as _impl
import sys as _sys
_sys.modules[__name__] = _impl
