"""Reexport. El código vive en core.certificados.certificado_artefacto."""
import core.certificados.certificado_artefacto as _impl
import sys as _sys
_sys.modules[__name__] = _impl
