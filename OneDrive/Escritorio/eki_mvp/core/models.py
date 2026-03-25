from django.db import models
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
import re
import openpyxl # <--- Nueva librería
import os
from django.db import IntegrityError

# 1. ESTUDIANTE
class Estudiante(models.Model):
    nombre = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, unique=True)
    activo = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def clean(self):
        # Limpieza de teléfono
        numero = re.sub(r'\D', '', str(self.telefono))
        if len(numero) == 10: numero = f"57{numero}"
        
        # Validación
        if not (10 <= len(numero) <= 15):
            # Si viene de un Excel, a veces es mejor no romper todo, 
            # pero aquí mantendremos la regla estricta.
            pass 
        self.telefono = numero

    def save(self, *args, **kwargs):
        self.clean() # Forzamos limpieza antes de guardar
        super().save(*args, **kwargs)

    def __str__(self): return f"{self.nombre} ({self.telefono})"

# 2. PLANTILLA
class Plantilla(models.Model):
    nombre_interno = models.CharField(max_length=100)
    cuerpo_mensaje = models.TextField()
    
    # Campos para mensajes con imágenes en WhatsApp
    tiene_imagen = models.BooleanField(default=False, help_text="¿Esta plantilla incluye una imagen?")
    url_imagen = models.URLField(max_length=500, blank=True, null=True, help_text="URL de la imagen a enviar")
    
    def __str__(self): return self.nombre_interno

# 3. CAMPAÑA
class Campana(models.Model):
    nombre = models.CharField(max_length=100)
    
    # NUEVO CAMPO: Subir Excel
    archivo_excel = models.FileField(
        upload_to='excels/', 
        blank=True, null=True,
        help_text="Sube un archivo .xlsx con columnas: 'Nombre' y 'Telefono'. Se agregarán automáticamente."
    )
    plantilla = models.ForeignKey(Plantilla, on_delete=models.PROTECT)
    destinatarios = models.ManyToManyField(Estudiante, blank=True) # blank=True para permitir guardar sin seleccionar manual

    # Canal de envío (sms, email, voz, whatsapp)
    CANAL_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('sms', 'SMS'),
        ('email', 'Email'),
        ('voz', 'Voz'),
    ]
    canal_envio = models.CharField(max_length=20, choices=CANAL_CHOICES, default='whatsapp')

    # Línea de origen (opcional)
    linea_origen = models.ForeignKey('Linea', null=True, blank=True, on_delete=models.SET_NULL)

    # Envío programado
    fecha_programada = models.DateTimeField(blank=True, null=True)

    ejecutada = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.nombre
    class Meta:
        verbose_name = 'Campaña'
        verbose_name_plural = 'Campañas'


# 3b. LINEAS (líneas de envío, e.g., cuentas de WhatsApp)
class Linea(models.Model):
    nombre = models.CharField(max_length=100, help_text='Etiqueta de la línea, p.ej. FKWhatsapp')
    numero = models.CharField(max_length=30, help_text='Número de la línea, p.ej. +573208198063')

    def __str__(self):
        return f"{self.nombre} ({self.numero})"

# 4. LOGS
class EnvioLog(models.Model):
    campana = models.ForeignKey(Campana, on_delete=models.CASCADE)
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE)
    estado = models.CharField(max_length=20, default='PENDIENTE')
    
    # 👇 ESTA ES LA LÍNEA QUE FALTABA, AGRÉGALA:
    respuesta_api = models.TextField(blank=True, null=True, help_text="Respuesta del servidor")
    
    fecha_envio = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.estudiante.nombre} - {self.estado}"


# Registro de mensajes enviados/recibidos por WhatsApp
class WhatsappLog(models.Model):
    telefono = models.CharField(max_length=30)
    mensaje = models.TextField(blank=True, null=True)
    mensaje_id = models.CharField(max_length=200, blank=True, null=True, db_index=True)
    estado = models.CharField(max_length=50, default='PENDING')
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.telefono} - {self.estado} ({self.mensaje_id})"


# ============================================================
# MÓDULO: ENTREGAS DIFERIDAS (DRIP CONTENT)
# ============================================================

class Curso(models.Model):
    """Curso educativo con soporte para entrega diferida de módulos."""
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    dias_espera_entre_modulos = models.IntegerField(
        default=0,
        help_text="Días de espera entre módulos (0 = sin espera, 7 = semanal)."
    )
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = 'Curso'
        verbose_name_plural = 'Cursos'


class Modulo(models.Model):
    """Módulo perteneciente a un curso."""
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='modulos')
    nombre = models.CharField(max_length=200)
    contenido = models.TextField(blank=True)
    orden = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.curso.nombre} - {self.nombre}"

    class Meta:
        verbose_name = 'Módulo'
        verbose_name_plural = 'Módulos'
        ordering = ['curso', 'orden']


class ProgresoEstudiante(models.Model):
    """Progreso de un estudiante en un curso (soporta Drip Content)."""

    ESTADO_CHOICES = [
        ('en_curso', 'En Curso'),
        ('completado', 'Completado'),
        ('bloqueado', 'Bloqueado'),
    ]

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='progresos')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    modulo_actual = models.ForeignKey(
        Modulo, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Módulo en el que se encuentra actualmente el estudiante."
    )
    fecha_ultimo_avance = models.DateTimeField(
        null=True, blank=True,
        help_text="Fecha en que el estudiante completó el último módulo."
    )
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='en_curso')
    fecha_inicio = models.DateTimeField(auto_now_add=True)

    def puede_avanzar(self):
        """
        Verifica si el estudiante puede avanzar al siguiente módulo.
        Retorna (bool, fecha_desbloqueo_o_None).
        """
        if self.curso.dias_espera_entre_modulos == 0:
            return True, None
        if not self.fecha_ultimo_avance:
            return True, None
        fecha_desbloqueo = self.fecha_ultimo_avance + timedelta(days=self.curso.dias_espera_entre_modulos)
        if timezone.now() >= fecha_desbloqueo:
            return True, None
        return False, fecha_desbloqueo

    def __str__(self):
        return f"{self.estudiante.nombre} - {self.curso.nombre} ({self.estado})"

    class Meta:
        unique_together = ('estudiante', 'curso')
        verbose_name = 'Progreso del Estudiante'
        verbose_name_plural = 'Progresos de Estudiantes'


# ============================================================
# MÓDULO: GAMIFICACIÓN GEOLOCALIZADA (MODO POKÉMON GO)
# ============================================================

class AliadoEmpleabilidad(models.Model):
    """Empresa aliada para el radar de empleabilidad geolocalizado."""
    nombre_empresa = models.CharField(max_length=200)
    latitud = models.FloatField()
    longitud = models.FloatField()
    vacantes_activas = models.BooleanField(default=True)
    codigo_secreto = models.CharField(
        max_length=50,
        help_text="Código que el estudiante debe enviar al encontrar la empresa."
    )
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return self.nombre_empresa

    class Meta:
        verbose_name = 'Aliado de Empleabilidad'
        verbose_name_plural = 'Aliados de Empleabilidad'


class LogroEstudiante(models.Model):
    """Logro / insignia ganada por un estudiante (gamificación)."""

    TIPO_CHOICES = [
        ('graduacion', 'Graduación'),
        ('empleabilidad', 'Empleabilidad'),
        ('modulo', 'Módulo Completado'),
        ('curso', 'Curso Completado'),
    ]

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='logros')
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)
    descripcion = models.CharField(max_length=200)
    fecha = models.DateTimeField(auto_now_add=True)
    aliado = models.ForeignKey(
        AliadoEmpleabilidad, on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text="Empresa aliada vinculada al logro (si aplica)."
    )

    def __str__(self):
        return f"{self.estudiante.nombre} - {self.tipo}"

    class Meta:
        verbose_name = 'Logro del Estudiante'
        verbose_name_plural = 'Logros de Estudiantes'


# ============================================================
# MÓDULO: PREGUNTAS ABIERTAS (EVALUACIÓN POR FACILITADORA)
# ============================================================

class PreguntaAbierta(models.Model):
    """Pregunta de respuesta libre al final de un módulo."""
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE, related_name='preguntas_abiertas')
    pregunta = models.TextField()
    orden = models.IntegerField(default=1)
    activa = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.modulo.nombre} - Pregunta {self.orden}"

    class Meta:
        verbose_name = 'Pregunta Abierta'
        verbose_name_plural = 'Preguntas Abiertas'
        ordering = ['modulo', 'orden']


class RespuestaAbierta(models.Model):
    """Respuesta de un estudiante a una pregunta abierta, calificable por la facilitadora."""
    pregunta = models.ForeignKey(PreguntaAbierta, on_delete=models.CASCADE, related_name='respuestas')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='respuestas_abiertas')
    respuesta = models.TextField()
    calificacion = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text="Calificación asignada por la facilitadora (ej. 0.00 – 5.00)."
    )
    comentario_facilitador = models.TextField(
        blank=True,
        help_text="Retroalimentación de la facilitadora."
    )
    fecha_respuesta = models.DateTimeField(auto_now_add=True)
    fecha_calificacion = models.DateTimeField(null=True, blank=True)
    calificado_por = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='calificaciones_abiertas'
    )

    def __str__(self):
        return f"{self.estudiante.nombre} → {self.pregunta}"

    class Meta:
        unique_together = ('pregunta', 'estudiante')
        verbose_name = 'Respuesta Abierta'
        verbose_name_plural = 'Respuestas Abiertas'


# Procesar Excel subido: crear Estudiantes y agregarlos a la campaña
@receiver(post_save, sender=Campana)
def procesar_excel_campana(sender, instance, created, **kwargs):
    # Si hay un archivo y no hay destinatarios, intentamos cargarlo
    if instance.archivo_excel and instance.destinatarios.count() == 0:
        try:
            file_path = instance.archivo_excel.path
            if os.path.exists(file_path):
                wb = openpyxl.load_workbook(file_path)
                sheet = wb.active
                # Esperamos: columna A = Nombre, columna B = Telefono
                for row in sheet.iter_rows(min_row=2, values_only=True):
                    if not row: 
                        continue
                    nombre = str(row[0]).strip() if row[0] is not None else ''
                    telefono = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ''
                    if not telefono:
                        continue
                    # Normalizamos y creamos/obtenemos estudiante
                    try:
                        estudiante, created_est = Estudiante.objects.get_or_create(telefono=telefono, defaults={'nombre': nombre})
                    except IntegrityError:
                        # Si falla por formato, intentamos limpiar y reintentar
                        telefono_clean = re.sub(r'\D', '', telefono)
                        if len(telefono_clean) == 10:
                            telefono_clean = f"57{telefono_clean}"
                        estudiante, created_est = Estudiante.objects.get_or_create(telefono=telefono_clean, defaults={'nombre': nombre})
                    # Añadimos a destinatarios
                    instance.destinatarios.add(estudiante)
                # Guardar para asegurar M2M
                instance.save()
        except Exception:
            # Si falla la lectura del excel no queremos romper el flujo de guardado
            pass