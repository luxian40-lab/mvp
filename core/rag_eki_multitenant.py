"""Reexport de fase H2. El código vive en core.agentes.rag_eki_multitenant."""
import core.agentes.rag_eki_multitenant as _impl
import sys as _sys
_sys.modules[__name__] = _impl
