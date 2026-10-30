"""Reexport de fase H2. El código vive en core.agentes.models_uso_llm."""
import core.agentes.models_uso_llm as _impl
import sys as _sys
_sys.modules[__name__] = _impl
