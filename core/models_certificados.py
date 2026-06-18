"""
Sistema de Certificados Digitales para eki
Generación automática de certificados al completar cursos
"""

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
import hashlib
import uuid


class Certificado(models.Model):
    """
    Certificado digital emitido al completar un curso
    Inspirado en Coursera, edX, etc.
    """
    # Identificación
    codigo_verificacion = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        help_text="Código único de verificación"
    )
    
    # Estudiante y Curso
    estudiante = models.ForeignKey(
        'Estudiante',
        on_delete=models.CASCADE,
        related_name='certificados'
    )
    curso = models.ForeignKey(
        'Curso',
        on_delete=models.CASCADE,
        related_name='certificados_emitidos'
    )
    
    # Datos Académicos
    calificacion_final = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Calificación final (0-100)"
    )
    fecha_inicio = models.DateField(
        help_text="Fecha de inicio del curso"
    )
    fecha_completado = models.DateField(
        default=timezone.now,
        help_text="Fecha de finalización del curso"
    )
    
    # Estado
    emitido = models.BooleanField(
        default=False,
        help_text="Si el certificado fue generado y enviado"
    )
    fecha_emision = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha de emisión del certificado"
    )
    
    # Archivo PDF
    archivo_pdf = models.FileField(
        upload_to='Certificadosestudiantes/',
        null=True,
        blank=True,
        help_text="Certificado en PDF"
    )
    
    # Archivo Imagen (alternativa al PDF)
    archivo_imagen = models.ImageField(
        upload_to='Certificadosestudiantes/',
        null=True,
        blank=True,
        help_text="Certificado en imagen (PNG/JPG)"
    )
    
    # Metadata
    enviado_whatsapp = models.BooleanField(
        default=False,
        help_text="Si fue enviado por WhatsApp"
    )
    fecha_envio = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Timestamps
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "📜 Certificado"
        verbose_name_plural = "📜 Certificados"
        ordering = ['-fecha_emision', '-creado_en']
        indexes = [
            models.Index(fields=['codigo_verificacion']),
            models.Index(fields=['estudiante', 'curso']),
        ]
    
    def __str__(self):
        return f"Certificado {self.codigo_verificacion} - {self.estudiante.nombre}"
    
    def save(self, *args, **kwargs):
        # Generar código de verificación si no existe
        if not self.codigo_verificacion:
            self.codigo_verificacion = self.generar_codigo_verificacion()
        super().save(*args, **kwargs)
    
    def generar_codigo_verificacion(self):
        """
        Genera código único de verificación
        Formato: eki-XXXX-YYYY-ZZZZ
        """
        # Crear hash único basado en datos
        datos = f"{self.estudiante.id}{self.curso.id}{timezone.now().isoformat()}{uuid.uuid4()}"
        hash_obj = hashlib.sha256(datos.encode())
        hash_hex = hash_obj.hexdigest()[:12].upper()
        
        # Formatear como eki-XXXX-YYYY-ZZZZ
        codigo = f"eki-{hash_hex[0:4]}-{hash_hex[4:8]}-{hash_hex[8:12]}"
        
        # Verificar que no exista (muy improbable)
        if Certificado.objects.filter(codigo_verificacion=codigo).exists():
            return self.generar_codigo_verificacion()
        
        return codigo
    
    def obtener_url_verificacion(self):
        """Retorna URL pública para verificar certificado en landing page"""
        base = (
            getattr(settings, "CERTIFICADO_VERIFICACION_BASE_URL", "")
            or "https://certificadosseki.netlify.app"
        ).rstrip("/")
        return f"{base}/?code={self.codigo_verificacion}"
    
    def obtener_mencion(self):
        """
        Retorna mención especial según calificación
        Similar a Coursera: With Distinction, etc.
        """
        if self.calificacion_final >= 95:
            return "Con Distinción Sobresaliente"
        elif self.calificacion_final >= 90:
            return "Con Distinción"
        elif self.calificacion_final >= 85:
            return "Con Honor"
        elif self.calificacion_final >= 80:
            return "Con Mérito"
        else:
            return None
    
    def duracion_curso(self):
        """Retorna duración del curso en días"""
        if self.fecha_inicio and self.fecha_completado:
            return (self.fecha_completado - self.fecha_inicio).days
        return 0


class PlantillaCertificado(models.Model):
    """
    Plantillas personalizables para certificados
    Permite diferentes diseños por tipo de curso o por cliente
    """
    nombre = models.CharField(
        max_length=100,
        help_text="Nombre identificador de la plantilla (ej: 'Plantilla Cargill', 'Plantilla TechnoServe')"
    )
    descripcion = models.TextField(
        blank=True,
        help_text="Descripción opcional de cuándo usar esta plantilla"
    )
    
    # 🏢 CLIENTE (para plantillas específicas de empresas)
    cliente = models.ForeignKey(
        'Cliente',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='plantillas_certificados',
        verbose_name='Cliente',
        help_text='Si es para un cliente específico. Dejar vacío = plantilla general de eki'
    )
    
    # � CURSO (para plantillas específicas de un curso)
    curso = models.ForeignKey(
        'Curso',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='plantillas_certificados',
        verbose_name='Curso',
        help_text='Curso específico para esta plantilla. Si se asigna, se usará automáticamente al completar este curso.'
    )
    
    # �📄 OPCIÓN 1: SUBIR PDF PERSONALIZADO (Recomendado para empresas)
    archivo_plantilla_pdf = models.FileField(
        upload_to='certificados/plantillas_personalizadas/',
        null=True,
        blank=True,
        help_text="📤 Sube tu propia plantilla en PDF. Solo necesita tener espacio para el NOMBRE del estudiante."
    )
    
    MODO_PLANTILLA_CHOICES = [
        ('imagen', 'Imagen (S3 / archivo con marcadores)'),
        ('diseno_eki', 'Diseño eki (colores y textos)'),
        ('pdf', 'PDF personalizado'),
    ]
    modo_plantilla = models.CharField(
        max_length=20,
        choices=MODO_PLANTILLA_CHOICES,
        default='imagen',
        verbose_name='Modo de plantilla',
        help_text='Define cómo se generará el certificado para esta plantilla.',
    )

    # 🖼️ OPCIÓN 1B: SUBIR IMAGEN/MULTIMEDIA (Alternativa al PDF)
    FORMATO_CERTIFICADO_CHOICES = [
        ('pdf', '📄 PDF'),
        ('imagen', '🖼️ Imagen (PNG/JPG)'),
    ]
    formato_certificado = models.CharField(
        max_length=10,
        choices=FORMATO_CERTIFICADO_CHOICES,
        default='pdf',
        help_text="Formato de salida del certificado"
    )
    archivo_plantilla_imagen = models.ImageField(
        upload_to='certificados/plantillas_imagenes/',
        null=True,
        blank=True,
        help_text="🖼️ Sube una plantilla en formato imagen (PNG/JPG). Se personalizará con el nombre del estudiante."
    )
    
    # 🔗 OPCIÓN 1C: URL DE IMAGEN EXTERNA (Alternativa a subir archivo)
    url_plantilla_imagen = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        help_text="🔗 URL directa a una imagen de plantilla (PNG/JPG). Usa esto si prefieres alojar la imagen externamente."
    )
    
    # 🎨 OPCIÓN 2: DISEÑO PERSONALIZADO CON eki (Si no subes PDF)
    # Diseño
    imagen_fondo = models.ImageField(
        upload_to='certificados/plantillas/',
        null=True,
        blank=True,
        help_text="Imagen de fondo del certificado (si no subes PDF)"
    )
    logo_institucion = models.ImageField(
        upload_to='certificados/logos/',
        null=True,
        blank=True,
        help_text="Logo de la institución"
    )
    
    # Colores (hex)
    color_primario = models.CharField(
        max_length=7,
        default='#2C3E50',
        help_text="Color principal (ej: #2C3E50)"
    )
    color_secundario = models.CharField(
        max_length=7,
        default='#3498DB',
        help_text="Color secundario"
    )
    
    # Textos personalizables
    texto_superior = models.CharField(
        max_length=200,
        default="eki - Soluciones Educativas",
        help_text="Texto en la parte superior"
    )
    texto_certificado = models.CharField(
        max_length=100,
        default="CERTIFICADO DE FINALIZACIÓN",
        help_text="Título del certificado"
    )
    
    # 📝 Variables para reemplazar en PDF personalizado
    variable_nombre = models.CharField(
        max_length=50,
        default="{nombre}",
        help_text="Variable a reemplazar por el nombre del estudiante (ej: {nombre}, [NOMBRE], {{nombre}})"
    )
    variable_curso = models.CharField(
        max_length=50,
        default="{curso}",
        help_text="Variable a reemplazar por el nombre del curso"
    )
    variable_fecha = models.CharField(
        max_length=50,
        default="{fecha}",
        help_text="Variable a reemplazar por la fecha"
    )
    
    # Estado
    activa = models.BooleanField(default=True)
    por_defecto = models.BooleanField(
        default=False,
        help_text="Plantilla por defecto para nuevos certificados"
    )
    
    # Timestamps
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "🎨 Plantilla de Certificado"
        verbose_name_plural = "🎨 Plantillas de Certificados"
        ordering = ['-por_defecto', 'nombre']
    
    def __str__(self):
        cliente_str = f" ({self.cliente.nombre})" if self.cliente else ""
        return f"{self.nombre}{cliente_str} {'(Por defecto)' if self.por_defecto else ''}"
    
    def modo_efectivo(self) -> str:
        modo = (self.modo_plantilla or '').strip()
        if modo in dict(self.MODO_PLANTILLA_CHOICES):
            return modo
        if self.archivo_plantilla_imagen or self.url_plantilla_imagen:
            return 'imagen'
        if self.archivo_plantilla_pdf:
            return 'pdf'
        return 'diseno_eki'

    def clean(self):
        """Validar y limpiar URL de plantilla para evitar duplicaciones y errores"""
        super().clean()
        modo = self.modo_efectivo()
        if modo == 'imagen' and not (self.archivo_plantilla_imagen or self.url_plantilla_imagen):
            raise ValidationError({
                'url_plantilla_imagen': (
                    'En modo Imagen debes subir un archivo o pegar la URL de S3 (.png/.jpg).'
                ),
            })
        if modo == 'pdf' and not self.archivo_plantilla_pdf:
            raise ValidationError({
                'archivo_plantilla_pdf': 'En modo PDF debes subir el archivo PDF personalizado.',
            })
        if self.url_plantilla_imagen:
            url = self.url_plantilla_imagen.strip()
            # Detectar URLs duplicadas pegadas (ej: "archivo.jpghttps://...archivo.jpg")
            # Patron: buscar 'https://' dentro del string despues del inicio
            partes_https = url.split('https://')
            if len(partes_https) > 2:
                # Hay multiples https:// — tomar la ultima URL completa
                url = 'https://' + partes_https[-1]
            elif len(partes_https) == 2 and not url.startswith('https://'):
                # Empieza con basura y luego tiene https://
                url = 'https://' + partes_https[1]
            # Asegurar que termina en extension de imagen valida
            url_lower = url.lower().split('?')[0]  # ignorar query params
            if not any(url_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                raise ValidationError({
                    'url_plantilla_imagen': 'La URL debe terminar en .png, .jpg, .jpeg o .webp'
                })
            # Validar que es una URL completa
            if not url.startswith('http://') and not url.startswith('https://'):
                raise ValidationError({
                    'url_plantilla_imagen': 'La URL debe comenzar con https://'
                })
            self.url_plantilla_imagen = url
        
        # Si se sube archivo Y hay URL, preferir archivo (limpiar URL para evitar conflicto)
        if self.archivo_plantilla_imagen and self.url_plantilla_imagen:
            # Ambos presentes: archivo tiene prioridad, pero dejar URL como backup
            pass

    def save(self, *args, **kwargs):
        # Ejecutar validacion de URL
        try:
            self.clean()
        except ValidationError:
            pass  # En save() no bloqueamos, solo en admin form
        # Si se marca como por defecto, desmarcar otras
        if self.por_defecto:
            PlantillaCertificado.objects.filter(por_defecto=True).exclude(pk=self.pk).update(por_defecto=False)
        super().save(*args, **kwargs)
    
    def usa_pdf_personalizado(self):
        """Verifica si esta plantilla usa un PDF personalizado"""
        return bool(self.archivo_plantilla_pdf)
    
    def usa_imagen_personalizada(self):
        """Verifica si esta plantilla usa una imagen personalizada (archivo o URL)"""
        return bool(self.archivo_plantilla_imagen) or bool(self.url_plantilla_imagen)
    
    def get_tipo_formato(self):
        """Retorna el formato de certificado efectivo"""
        if self.archivo_plantilla_imagen or self.url_plantilla_imagen:
            return 'imagen'
        if self.archivo_plantilla_pdf:
            return 'pdf'
        return self.formato_certificado
