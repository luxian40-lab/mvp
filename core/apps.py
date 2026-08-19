from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Core'
    
    def ready(self):
        """Importar signals al iniciar la app"""
        # Gamificación activada
        import core.gamificacion  # Crea perfil automáticamente
        import core.signals_gamificacion  # Otorga puntos/badges
        import core.signals_eventos_ia  # Eventos IA observables
        
        # Compresión automática de videos
        import core.signals_videos
        
        # Certificados automáticos
        import core.signals_certificados  # Genera certificado al completar curso
        
        # Base de conocimientos para IAs
        import core.signals_conocimientos  # Actualiza conocimientos cuando se modifican cursos

        # Telemetría Centro de Éxito (eventos de aprendizaje)
        import core.signals_telemetria

        import core.signals_publicacion_wa  # Slack borrador en curso activo
