"""Staticfiles: manifiesto hashed, pero NUNCA 500 si falta una entrada (favicon, OG, CSS)."""

from urllib.parse import unquote, urlsplit

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

    def stored_name(self, name):
        # Sin entrada en el manifiesto, Django calcula un hash y lo pone en la URL
        # aunque collectstatic no haya escrito ese archivo. El navegador pide
        # styles.<hash>.css, en disco solo está styles.css, y los iconos salen
        # como texto (home, unfold_more).
        clean_name = urlsplit(unquote(name)).path.strip()
        if self.hash_key(clean_name) not in self.hashed_files:
            return clean_name
        return super().stored_name(name)
