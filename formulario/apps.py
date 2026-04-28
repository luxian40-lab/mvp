from django.apps import AppConfig


class FormularioConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "formulario"
    verbose_name = "Formularios GEI (recolección de datos)"

    def ready(self) -> None:
        import formulario.signals  # noqa: F401, PLC0415
