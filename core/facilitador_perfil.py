"""Reexport de fase H2. El código vive en core.curso.facilitador_perfil."""
import core.curso.facilitador_perfil as _impl
import sys as _sys
_sys.modules[__name__] = _impl
