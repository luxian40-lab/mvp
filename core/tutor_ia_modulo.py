"""Reexport de fase H2. El código vive en core.agentes.tutor_ia_modulo."""
import core.agentes.tutor_ia_modulo as _impl
import sys as _sys
_sys.modules[__name__] = _impl
