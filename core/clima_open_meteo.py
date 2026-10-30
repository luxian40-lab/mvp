"""Reexport de fase H2. El código vive en core.analitica.clima_open_meteo."""
import core.analitica.clima_open_meteo as _impl
import sys as _sys
_sys.modules[__name__] = _impl
