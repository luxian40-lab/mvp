"""
Sistema de Recompensas Configurables
Permite al equipo de EKI crear recompensas desde Django Admin sin programar
"""

from django.db import models
from django.core.validators import MinValueValidator
from .models import Estudiante


class Recompensa(models.Model):
    """
    Recompensas que estudiantes pueden canjear con sus puntos
    Totalmente configurable desde Django Admin
    """
    
    TIPO_CHOICES = [
        ('DIGITAL', 'Digital (PDF, Video, Guía)'),
        ('DESCUENTO', 'Descuento en Productos'),
        ('CERTIFICADO', 'Certificado Especial'),
        ('CONSULTORIA', 'Consultoría 1-a-1'),
        ('ACCESO', 'Acceso a Contenido Premium'),
        ('FISICO', 'Producto Físico (Semillas, Herramientas)'),
        ('EVENTO', 'Entrada a Evento'),
        ('OTRO', 'Otro'),
    ]
    
    ESTADO_CHOICES = [
        ('DISPONIBLE', 'Disponible'),
        ('AGOTADO', 'Agotado'),
        ('PROXIMO', 'Próximamente'),
        ('INACTIVO', 'Inactivo'),
    ]
    
    # Información básica
    nombre = models.CharField(max_length=200, help_text="Nombre de la recompensa")
    descripcion = models.TextField(help_text="Descripción detallada de la recompensa")
    icono = models.CharField(max_length=10, default='🎁', help_text="Emoji para mostrar")
    imagen_url = models.URLField(blank=True, null=True, help_text="URL de imagen promocional")
    
    # Tipo y costo
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='DIGITAL')
    puntos_requeridos = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Puntos que cuesta canjear esta recompensa"
    )
    
    # Disponibilidad
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='DISPONIBLE')
    cantidad_disponible = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Dejar vacío para cantidad ilimitada"
    )
    cantidad_canjeada = models.IntegerField(default=0, editable=False)
    
    # Restricciones
    nivel_minimo = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Nivel mínimo del estudiante para canjear (opcional)"
    )
    fecha_inicio = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha desde cuando está disponible (opcional)"
    )
    fecha_fin = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha hasta cuando está disponible (opcional)"
    )
    
    # Cumplimiento
    instrucciones_entrega = models.TextField(
        blank=True,
        help_text="Instrucciones para entregar la recompensa al estudiante"
    )
    enlace_descarga = models.URLField(
        blank=True,
        help_text="Link directo para recompensas digitales"
    )
    
    # Metadata
    orden = models.IntegerField(default=0, help_text="Orden de aparición en catálogo")
    destacado = models.BooleanField(default=False, help_text="Mostrar como destacado")
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Recompensa"
        verbose_name_plural = "Recompensas"
        ordering = ['-destacado', 'orden', 'puntos_requeridos']
    
    def __str__(self):
        return f"{self.icono} {self.nombre} ({self.puntos_requeridos} pts)"
    
    def esta_disponible(self):
        """Verifica si la recompensa está disponible para canjear"""
        from django.utils import timezone
        
        # Estado debe ser disponible
        if self.estado != 'DISPONIBLE' or not self.activo:
            return False
        
        # Verificar cantidad
        if self.cantidad_disponible is not None:
            if self.cantidad_canjeada >= self.cantidad_disponible:
                return False
        
        # Verificar fechas
        ahora = timezone.now()
        if self.fecha_inicio and ahora < self.fecha_inicio:
            return False
        if self.fecha_fin and ahora > self.fecha_fin:
            return False
        
        return True
    
    def cantidad_restante(self):
        """Retorna cantidad restante o None si es ilimitado"""
        if self.cantidad_disponible is None:
            return None
        return max(0, self.cantidad_disponible - self.cantidad_canjeada)
    
    def puede_canjear(self, estudiante):
        """Verifica si un estudiante específico puede canjear esta recompensa"""
        from .gamificacion import PerfilGamificacion
        
        # Recompensa disponible
        if not self.esta_disponible():
            return False, "Recompensa no disponible"
        
        # Perfil del estudiante
        try:
            perfil = PerfilGamificacion.objects.get(estudiante=estudiante)
        except PerfilGamificacion.DoesNotExist:
            return False, "Perfil de gamificación no encontrado"
        
        # Puntos suficientes
        if perfil.puntos_totales < self.puntos_requeridos:
            return False, f"Necesitas {self.puntos_requeridos - perfil.puntos_totales} puntos más"
        
        # Nivel mínimo
        if self.nivel_minimo and perfil.nivel < self.nivel_minimo:
            return False, f"Necesitas nivel {self.nivel_minimo} (tienes nivel {perfil.nivel})"
        
        return True, "Puede canjear"


class CanjeRecompensa(models.Model):
    """
    Registro de recompensas canjeadas por estudiantes
    """
    
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente de Entrega'),
        ('PROCESANDO', 'Procesando'),
        ('ENTREGADO', 'Entregado'),
        ('CANCELADO', 'Cancelado'),
    ]
    
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='recompensas_canjeadas'
    )
    recompensa = models.ForeignKey(
        Recompensa,
        on_delete=models.CASCADE,
        related_name='canjes'
    )
    
    # Detalles del canje
    puntos_gastados = models.IntegerField(help_text="Puntos gastados en este canje")
    fecha_canje = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    
    # Cumplimiento
    fecha_entrega = models.DateTimeField(null=True, blank=True)
    nota_entrega = models.TextField(
        blank=True,
        help_text="Notas sobre la entrega (tracking, confirmación, etc.)"
    )
    
    # Metadata
    atendido_por = models.CharField(
        max_length=100,
        blank=True,
        help_text="Miembro del equipo EKI que procesó el canje"
    )
    
    class Meta:
        verbose_name = "Canje de Recompensa"
        verbose_name_plural = "Canjes de Recompensas"
        ordering = ['-fecha_canje']
    
    def __str__(self):
        return f"{self.estudiante.nombre} - {self.recompensa.nombre} ({self.fecha_canje.strftime('%Y-%m-%d')})"
    
    def marcar_entregado(self, nota=""):
        """Marca el canje como entregado"""
        from django.utils import timezone
        self.estado = 'ENTREGADO'
        self.fecha_entrega = timezone.now()
        if nota:
            self.nota_entrega = nota
        self.save()


# Señal para descontar puntos al canjear
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=CanjeRecompensa)
def descontar_puntos_canje(sender, instance, created, **kwargs):
    """Descuenta puntos del perfil cuando se canjea una recompensa"""
    if created:
        from .gamificacion import PerfilGamificacion, TransaccionPuntos
        
        perfil = PerfilGamificacion.objects.get(estudiante=instance.estudiante)
        
        # Descontar puntos (agregar_puntos con negativo)
        perfil.agregar_puntos(
            puntos=-instance.puntos_gastados,
            razon=f"Canjeó: {instance.recompensa.nombre}",
            tipo='GASTO'
        )
        
        # Incrementar contador de canjes en la recompensa
        instance.recompensa.cantidad_canjeada += 1
        instance.recompensa.save()
