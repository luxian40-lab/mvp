"""Reexport de fase H2. El código vive en core.agentes.generador_ejercicios_ia."""
import core.agentes.generador_ejercicios_ia as _impl
import sys as _sys
_sys.modules[__name__] = _impl
