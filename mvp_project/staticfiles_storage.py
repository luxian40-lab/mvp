"""Staticfiles: manifiesto hashed, pero NUNCA 500 si falta una entrada (favicon, OG, CSS)."""

from whitenoise.storage import CompressedManifestStaticFilesStorage


class EkiManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Django por defecto (manifest_strict=True) tumba el admin si collectstatic no corrió."""

    manifest_strict = False
