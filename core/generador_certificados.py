"""Reexport de fase H2. El código vive en core.certificados.generador_certificados."""
import core.certificados.generador_certificados as _impl
import sys as _sys
_sys.modules[__name__] = _impl
