"""
Sistema de Gamificación para EKI
Sistema de puntos, badges, rankings y rachas para motivar a estudiantes campesinos
Desarrollado para Andrés Rubiano - EKI
"""

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import Estudiante, Curso


class PerfilGamificacion(models.Model):
    """Perfil de gamificación del estudiante"""
    estudiante = models.OneToOneField(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='perfil_gamificacion'
    )
    
    # Puntos y nivel
    puntos_totales = models.IntegerField(
        default=0,
        help_text='Puntos acumulados totales'
    )
    nivel = models.IntegerField(
        default=1,
        help_text='Nivel actual del estudiante'
    )
    experiencia_nivel_actual = models.IntegerField(
        default=0,
        help_text='Experiencia en el nivel actual'
    )
    
    # Rachas
    racha_dias_actual = models.IntegerField(
        default=0,
        help_text='Días consecutivos de actividad actual'
    )
    racha_dias_maxima = models.IntegerField(
        default=0,
        help_text='Récord de días consecutivos'
    )
    ultima_actividad = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Última vez que tuvo actividad'
    )
    
    # Estadísticas
    modulos_completados = models.IntegerField(default=0)
    examenes_aprobados = models.IntegerField(default=0)
    preguntas_respondidas = models.IntegerField(default=0)
    audios_enviados = models.IntegerField(default=0)
    
    # Ranking
    posicion_ranking = models.IntegerField(
        default=0,
        help_text='Posición en el ranking global'
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Perfil de Gamificación'
        verbose_name_plural = 'Perfiles de Gamificación'
        ordering = ['-puntos_totales']
    
    def __str__(self):
        return f"{self.estudiante.nombre} - Nivel {self.nivel} ({self.puntos_totales} pts)"
    
    def get_badges(self):
        """Retorna los badges del estudiante"""
        return self.estudiante.badges_obtenidos.all()
    
    def calcular_nivel(self):
        """Calcula el nivel basado en puntos totales"""
        # Cada nivel requiere más puntos: nivel 1 = 0-100, nivel 2 = 100-250, etc.
        nivel_anterior = self.nivel
        
        if self.puntos_totales < 100:
            nuevo_nivel = 1
        elif self.puntos_totales < 250:
            nuevo_nivel = 2
        elif self.puntos_totales < 500:
            nuevo_nivel = 3
        elif self.puntos_totales < 1000:
            nuevo_nivel = 4
        elif self.puntos_totales < 2000:
            nuevo_nivel = 5
        elif self.puntos_totales < 3500:
            nuevo_nivel = 6
        elif self.puntos_totales < 5500:
            nuevo_nivel = 7
        elif self.puntos_totales < 8000:
            nuevo_nivel = 8
        elif self.puntos_totales < 11000:
            nuevo_nivel = 9
        else:
            nuevo_nivel = 10
        
        self.nivel = nuevo_nivel
        
        # Calcular experiencia en el nivel actual
        limites_nivel = [0, 100, 250, 500, 1000, 2000, 3500, 5500, 8000, 11000, 999999]
        limite_inferior = limites_nivel[nuevo_nivel - 1]
        limite_superior = limites_nivel[nuevo_nivel]
        
        self.experiencia_nivel_actual = self.puntos_totales - limite_inferior
        
        # Si subió de nivel, otorgar badge
        if nuevo_nivel > nivel_anterior:
            self._otorgar_badge_nivel(nuevo_nivel)
        
        self.save()
        return nuevo_nivel
    
    def agregar_puntos(self, puntos, razon="Actividad"):
        """Agrega puntos y actualiza nivel"""
        self.puntos_totales += puntos
        nivel_anterior = self.nivel
        self.calcular_nivel()
        
        # Registrar transacción
        TransaccionPuntos.objects.create(
            perfil=self,
            puntos=puntos,
            tipo='GANANCIA',
            razon=razon
        )
        
        return self.nivel > nivel_anterior  # True si subió de nivel
    
    def actualizar_racha(self):
        """Actualiza la racha de días consecutivos"""
        ahora = timezone.now()
        
        if not self.ultima_actividad:
            # Primera actividad
            self.racha_dias_actual = 1
            self.ultima_actividad = ahora
            self.save()
            return True
        
        # Calcular diferencia en días
        dias_desde_ultima = (ahora.date() - self.ultima_actividad.date()).days
        
        if dias_desde_ultima == 0:
            # Misma fecha, no hacer nada
            return False
        elif dias_desde_ultima == 1:
            # Consecutivo! Aumentar racha
            self.racha_dias_actual += 1
            
            # Actualizar récord
            if self.racha_dias_actual > self.racha_dias_maxima:
                self.racha_dias_maxima = self.racha_dias_actual
            
            # Otorgar badges de racha
            if self.racha_dias_actual == 3:
                self._otorgar_badge_racha(3)
            elif self.racha_dias_actual == 7:
                self._otorgar_badge_racha(7)
                self.agregar_puntos(200, "Racha de 7 días")
            elif self.racha_dias_actual == 30:
                self._otorgar_badge_racha(30)
                self.agregar_puntos(1000, "Racha de 30 días")
            
            self.ultima_actividad = ahora
            self.save()
            return True
        else:
            # Se rompió la racha
            self.racha_dias_actual = 1
            self.ultima_actividad = ahora
            self.save()
            return False
    
    def _otorgar_badge_nivel(self, nivel):
        """Otorga badge por alcanzar un nivel"""
        try:
            badge = Badge.objects.get(tipo='NIVEL', nivel_requerido=nivel)
            BadgeEstudiante.objects.get_or_create(
                estudiante=self.estudiante,
                badge=badge
            )
        except Badge.DoesNotExist:
            pass
    
    def _otorgar_badge_racha(self, dias):
        """Otorga badge por racha"""
        try:
            badge = Badge.objects.get(tipo='RACHA', valor_requerido=dias)
            BadgeEstudiante.objects.get_or_create(
                estudiante=self.estudiante,
                badge=badge
            )
        except Badge.DoesNotExist:
            pass
    
    def porcentaje_nivel(self):
        """Retorna el porcentaje de progreso en el nivel actual"""
        limites_nivel = [0, 100, 250, 500, 1000, 2000, 3500, 5500, 8000, 11000, 999999]
        limite_inferior = limites_nivel[self.nivel - 1]
        limite_superior = limites_nivel[self.nivel]
        
        rango = limite_superior - limite_inferior
        progreso = self.puntos_totales - limite_inferior
        
        return int((progreso / rango) * 100)
    
    def puntos_para_siguiente_nivel(self):
        """Puntos que faltan para el siguiente nivel"""
        limites_nivel = [0, 100, 250, 500, 1000, 2000, 3500, 5500, 8000, 11000, 999999]
        if self.nivel >= 10:
            return 0
        limite_superior = limites_nivel[self.nivel]
        return limite_superior - self.puntos_totales


class Badge(models.Model):
    """Badges/insignias que pueden ganar los estudiantes"""
    TIPO_CHOICES = [
        ('NIVEL', 'Por alcanzar nivel'),
        ('RACHA', 'Por mantener racha'),
        ('CURSO', 'Por completar curso'),
        ('EXAMEN', 'Por aprobar examen'),
        ('PARTICIPACION', 'Por participación activa'),
        ('ESPECIAL', 'Badge especial'),
    ]
    
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    icono = models.CharField(
        max_length=10,
        default='🏆',
        help_text='Emoji del badge'
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    
    # Criterios para obtenerlo
    nivel_requerido = models.IntegerField(
        null=True,
        blank=True,
        help_text='Nivel necesario (solo para tipo NIVEL)'
    )
    valor_requerido = models.IntegerField(
        null=True,
        blank=True,
        help_text='Valor requerido (días de racha, cursos completados, etc.)'
    )
    curso_requerido = models.ForeignKey(
        Curso,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text='Curso específico requerido'
    )
    
    puntos_bonus = models.IntegerField(
        default=0,
        help_text='Puntos extra al obtener este badge'
    )
    
    es_secreto = models.BooleanField(
        default=False,
        help_text='Si es secreto, no se muestra hasta obtenerlo'
    )
    
    orden = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Badge'
        verbose_name_plural = 'Badges'
        ordering = ['orden', 'nombre']
    
    def __str__(self):
        return f"{self.icono} {self.nombre}"
    
    def total_obtenidos(self):
        """Cuántos estudiantes lo han obtenido"""
        return BadgeEstudiante.objects.filter(badge=self).count()


class BadgeEstudiante(models.Model):
    """Relación entre estudiantes y badges obtenidos"""
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name='badges_obtenidos'
    )
    badge = models.ForeignKey(
        Badge,
        on_delete=models.CASCADE,
        related_name='estudiantes'
    )
    fecha_obtenido = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Badge de Estudiante'
        verbose_name_plural = 'Badges de Estudiantes'
        unique_together = ['estudiante', 'badge']
        ordering = ['-fecha_obtenido']
    
    def __str__(self):
        return f"{self.estudiante.nombre} - {self.badge.nombre}"


class TransaccionPuntos(models.Model):
    """Historial de transacciones de puntos"""
    TIPO_CHOICES = [
        ('GANANCIA', 'Ganó puntos'),
        ('GASTO', 'Gastó puntos'),
        ('BONUS', 'Bonus especial'),
    ]
    
    perfil = models.ForeignKey(
        PerfilGamificacion,
        on_delete=models.CASCADE,
        related_name='transacciones'
    )
    puntos = models.IntegerField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    razon = models.CharField(max_length=200)
    fecha = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Transacción de Puntos'
        verbose_name_plural = 'Transacciones de Puntos'
        ordering = ['-fecha']
    
    def __str__(self):
        signo = '+' if self.tipo in ['GANANCIA', 'BONUS'] else '-'
        return f"{self.perfil.estudiante.nombre}: {signo}{self.puntos} pts - {self.razon}"


# Señales para crear perfil automáticamente
@receiver(post_save, sender=Estudiante)
def crear_perfil_gamificacion(sender, instance, created, **kwargs):
    """Crea perfil de gamificación automáticamente"""
    if created:
        PerfilGamificacion.objects.get_or_create(estudiante=instance)
