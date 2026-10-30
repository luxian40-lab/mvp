from django.apps import AppConfig


class AprendeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'aprende'
    verbose_name = 'Aula web eki'

    def ready(self) -> None:
        import aprende.registro_core  # noqa: F401, PLC0415
