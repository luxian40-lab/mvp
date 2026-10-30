"""Reexport de fase H2. El código vive en core.certificados.certificado_diseno_eki."""
import core.certificados.certificado_diseno_eki as _impl
import sys as _sys
_sys.modules[__name__] = _impl
