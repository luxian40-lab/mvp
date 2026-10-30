"""Reexport de fase H2. El código vive en core.certificados.utils_certificados."""
import core.certificados.utils_certificados as _impl
import sys as _sys
_sys.modules[__name__] = _impl
