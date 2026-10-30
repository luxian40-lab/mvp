from django.apps import AppConfig


class PortalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'portal'
    verbose_name = 'Portal clientes'

    def ready(self) -> None:
        import portal.registro_core  # noqa: F401, PLC0415
