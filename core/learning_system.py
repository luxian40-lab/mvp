"""Reexport de fase H2. El código vive en core.agentes.learning_system."""
import core.agentes.learning_system as _impl
import sys as _sys
_sys.modules[__name__] = _impl
