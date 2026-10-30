"""Reexport de fase H2. El código vive en core.agentes.presupuesto_llm."""
import core.agentes.presupuesto_llm as _impl
import sys as _sys
_sys.modules[__name__] = _impl
