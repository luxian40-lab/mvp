"""Reexport de fase H2. El código vive en core.conversacion.onboarding_audio_handler."""
import core.conversacion.onboarding_audio_handler as _impl
import sys as _sys
_sys.modules[__name__] = _impl
