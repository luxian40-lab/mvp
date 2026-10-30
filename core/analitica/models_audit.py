"""
Modelo para Audit Log - Registra todas las acciones con certificados
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class AuditLog(models.Model):
    """Registra todas las acciones sobre certificados para auditoría"""
    
    ACCION_CHOICES = [
        ('GENERAR', 'Generar certificado'),
        ('ENVIAR', 'Enviar por WhatsApp'),
        ('DESCARGAR', 'Descargar PDF'),
        ('VERIFICAR', 'Verificar (público)'),
        ('MODIFICAR', 'Modificar detalles'),
        ('ELIMINAR', 'Eliminar'),
        ('REGENERAR', 'Regenerar PDF'),
        ('AUTO_GENERAR', 'Auto-generar (signal)'),
        ('ERROR', 'Error en proceso'),
    ]
    
    # Información de la acción
    accion = models.CharField(
        max_length=20,
        choices=ACCION_CHOICES,
        verbose_name='Acción'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción',
        help_text='Detalles adicionales de la acción'
    )
    
    # Relacionado a certificado
    certificado_codigo = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Código de Certificado'
    )
    estudiante_nombre = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Nombre del Estudiante'
    )
    curso_nombre = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Nombre del Curso'
    )
    
    # Quién lo hizo (si es aplicable)
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Usuario',
        help_text='Usuario que realizó la acción (vacío si fue automático)'
    )
    
    # Dirección IP (para accesos públicos)
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='Dirección IP'
    )
    
    # Estado del resultado
    exitoso = models.BooleanField(
        default=True,
        verbose_name='Exitoso'
    )
    mensaje_error = models.TextField(
        blank=True,
        verbose_name='Mensaje de Error'
    )
    
    # Timestamps
    fecha_accion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Acción'
    )
    
    class Meta:
        verbose_name = 'Auditoría'
        verbose_name_plural = '🔐 Sistema → Auditoría'
        ordering = ['-fecha_accion']
        indexes = [
            models.Index(fields=['-fecha_accion']),
            models.Index(fields=['accion']),
            models.Index(fields=['certificado_codigo']),
        ]
    
    def __str__(self):
        return f"{self.get_accion_display()} - {self.certificado_codigo or 'N/A'} ({self.fecha_accion.strftime('%d/%m/%Y %H:%M')})"
    
    @classmethod
    def registrar(cls, accion, estudiante=None, curso=None, certificado=None, 
                  usuario=None, ip_address=None, exitoso=True, mensaje_error=''):
        """
        Registra una acción en el audit log
        
        Args:
            accion: Tipo de acción (ver ACCION_CHOICES)
            estudiante: Objeto Estudiante o nombre
            curso: Objeto Curso o nombre
            certificado: Objeto Certificado o código
            usuario: Usuario que realizó la acción
            ip_address: IP desde donde se realizó
            exitoso: Si la acción fue exitosa
            mensaje_error: Mensaje de error si aplica
        """
        registro = cls()
        registro.accion = accion
        
        # Procesar estudiante
        if estudiante:
            if hasattr(estudiante, 'nombre'):
                registro.estudiante_nombre = estudiante.nombre
            else:
                registro.estudiante_nombre = str(estudiante)
        
        # Procesar curso
        if curso:
            if hasattr(curso, 'nombre'):
                registro.curso_nombre = curso.nombre
            else:
                registro.curso_nombre = str(curso)
        
        # Procesar certificado
        if certificado:
            if hasattr(certificado, 'codigo_verificacion'):
                registro.certificado_codigo = certificado.codigo_verificacion
            else:
                registro.certificado_codigo = str(certificado)
        
        registro.usuario = usuario
        registro.ip_address = ip_address
        registro.exitoso = exitoso
        registro.mensaje_error = mensaje_error
        
        registro.save()
        return registro
    
    def get_resumen(self):
        """Retorna un resumen legible de la acción"""
        partes = [f"{self.get_accion_display()}"]
        if self.certificado_codigo:
            partes.append(f"({self.certificado_codigo})")
        if self.estudiante_nombre:
            partes.append(f"- {self.estudiante_nombre}")
        return " ".join(partes)
