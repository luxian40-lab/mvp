"""Staticfiles: manifiesto hashed, pero NUNCA 500 si falta una entrada (favicon, OG, CSS)."""

from whitenoise.storage import CompressedManifestStaticFilesStorage


class EkiManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Django por defecto (manifest_strict=True) tumba el admin si collectstatic no corrió."""

    manifest_strict = False

    def hashed_name(self, name, content=None, filename=None):
        # WhiteNoise/Django levantan ValueError si el archivo no está en STATIC_ROOT
        # (p.ej. tras setenv sin collectstatic completo). Nunca tumbar la página.
        try:
            return super().hashed_name(name, content, filename)
        except ValueError:
            return name
