"""Modelos de conocimiento (fase H1).

Movidos tal cual desde core/models/__init__.py, que los reexporta:
importar desde core.models sigue igual.
"""
from django.db import models
import os
from core.models.clientes import Cliente
from core.models.cursos import Curso


class DocumentoRAG(models.Model):
    """
    Documento subido para el sistema RAG Multi-Tenant.
    Cada documento se asocia a un Curso (y por extensión a su Cliente).
    Los agentes IA usan estos documentos para responder preguntas.
    
    Aislamiento: Solo el curso al que pertenece puede acceder a este documento.
    """
    TIPO_CHOICES = [
        ('contenido', 'Contenido del Curso'),
        ('manual', 'Manual / Documentación'),
        ('faq', 'Preguntas Frecuentes'),
        ('guia', 'Guía Práctica'),
        ('normativa', 'Normativa / Regulación'),
    ]
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente de indexar'),
        ('indexado', 'Indexado en RAG'),
        ('error', 'Error al indexar'),
    ]

    curso = models.ForeignKey(
        Curso,
        on_delete=models.CASCADE,
        related_name='documentos_rag',
        verbose_name='Curso',
        help_text='Curso al que pertenece este documento. Los agentes IA SOLO verán documentos de su curso.'
    )
    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre del documento',
        help_text='Identificador único (ej: Manual_Tomates_v1, FAQ_Café)'
    )
    archivo = models.FileField(
        upload_to='documentos_rag/%Y/%m/',
        verbose_name='Archivo (PDF, DOCX, TXT, XLSX)',
        help_text='Formatos soportados: .pdf, .docx, .txt, .xlsx, .xlsm (Excel; listas de precios)',
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='contenido',
        verbose_name='Tipo de documento'
    )
    uso_agente = models.CharField(
        max_length=20,
        choices=[
            ('todos', 'Todos los agentes (compartido)'),
            ('companero', 'Extra compañero (Darío / Carlos)'),
            ('claudia', 'Extra Claudia (facilitadora)'),
        ],
        default='todos',
        verbose_name='Uso del documento',
        help_text=(
            'todos = Course Engine y todos los agentes edu. '
            'companero/claudia = extra encima de todos, no oculta el material compartido.'
        ),
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name='Estado RAG'
    )
    chunks_indexados = models.IntegerField(
        default=0,
        verbose_name='Chunks indexados',
        help_text='Cantidad de fragmentos indexados en la BD vectorial'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción',
        help_text='Descripción opcional del contenido del documento'
    )
    fecha_subida = models.DateTimeField(auto_now_add=True)
    fecha_indexado = models.DateTimeField(null=True, blank=True)
    subido_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Subido por'
    )

    class Meta:
        ordering = ['-fecha_subida']
        verbose_name = 'Documento RAG'
        verbose_name_plural = 'Documentos RAG (Base de Conocimiento IA)'
        unique_together = ['curso', 'nombre']
        indexes = [
            models.Index(fields=['curso', 'estado']),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.curso.nombre})"

    @property
    def cliente_id(self):
        return self.curso.cliente_id if self.curso.cliente_id else 0

    def indexar(self):
        """Indexa este documento en ChromaDB para el cliente+curso.

        En producción el FileField vive en S3: `.path` lanza
        NotImplementedError ("This backend doesn't support absolute paths").
        Hay que bajar a un temporal, igual que DocumentoRAGComercial.
        """
        from core.rag_manager import rag_manager
        from django.utils import timezone

        if not self.archivo:
            self.estado = 'error'
            self.save(update_fields=['estado'])
            return 0

        ruta_temp = None
        try:
            ruta = None
            try:
                # Solo válido en storage local; en S3 esto lanza.
                if hasattr(self.archivo, 'path') and os.path.exists(self.archivo.path):
                    ruta = self.archivo.path
            except Exception:
                ruta = None

            if not ruta:
                ruta_temp = self._descargar_temp()
                ruta = ruta_temp

            if not ruta:
                self.estado = 'error'
                self.save(update_fields=['estado'])
                return 0

            n_chunks = rag_manager.procesar_documento(
                cliente_id=self.cliente_id,
                curso_id=self.curso_id,
                ruta_archivo=ruta,
                nombre_documento=self.nombre,
                tipo=self.tipo,
                uso=getattr(self, 'uso_agente', None) or 'todos',
            )
            self.chunks_indexados = n_chunks
            self.estado = 'indexado' if n_chunks > 0 else 'error'
            self.fecha_indexado = timezone.now()
            self.save(update_fields=['chunks_indexados', 'estado', 'fecha_indexado'])
            return n_chunks
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[DocumentoRAG] Error indexando {self.nombre}: {e}")
            self.estado = 'error'
            self.save(update_fields=['estado'])
            return 0
        finally:
            if ruta_temp:
                try:
                    os.unlink(ruta_temp)
                except Exception:
                    pass

    def _descargar_temp(self):
        """Descarga archivo desde storage (S3) a /tmp para procesamiento."""
        import tempfile
        try:
            ext = os.path.splitext(self.archivo.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                for chunk in self.archivo.chunks():
                    tmp.write(chunk)
                return tmp.name
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[DocumentoRAG] Error descargando {self.nombre}: {e}")
            return None


class DocumentoRAGComercial(models.Model):
    """
    Documento para el RAG comercial.
    Aislado del RAG de cursos para evitar mezclar conocimiento educativo y comercial.
    """
    CANAL_CHOICES = [
        ('bot_comercial', 'Bot Comercial WhatsApp'),
    ]
    TIPO_CHOICES = [
        ('producto', 'Producto / Catálogo'),
        ('precio', 'Precio / Lista comercial'),
        ('informe_tecnico', 'Informe técnico (ICA / ensayos)'),
        ('faq', 'Preguntas frecuentes comerciales'),
        ('politica', 'Políticas comerciales'),
        ('promo', 'Promociones'),
        ('general', 'Información general comercial'),
    ]
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente de indexar'),
        ('indexado', 'Indexado en RAG comercial'),
        ('error', 'Error al indexar'),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documentos_rag_comercial',
        verbose_name='Cliente',
        help_text='Cliente comercial del documento. Vacío = comercial general.'
    )
    canal = models.CharField(
        max_length=40,
        choices=CANAL_CHOICES,
        default='bot_comercial',
        verbose_name='Canal comercial'
    )
    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre del documento',
        help_text='Identificador único por cliente/canal (ej: catalogo_abril_2026).'
    )
    archivo = models.FileField(
        upload_to='documentos_rag_comercial/%Y/%m/',
        verbose_name='Archivo (PDF, DOCX, TXT, XLSX)',
        help_text='Formatos soportados: .pdf, .docx, .txt, .xlsx, .xlsm (Excel; listas de precios)',
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='producto',
        verbose_name='Tipo de documento'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendiente',
        verbose_name='Estado RAG'
    )
    chunks_indexados = models.IntegerField(
        default=0,
        verbose_name='Chunks indexados',
        help_text='Cantidad de fragmentos indexados en la BD vectorial comercial.'
    )
    error_indexacion = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='Motivo del último fallo de indexación RAG.',
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción',
        help_text='Descripción opcional del contenido comercial.'
    )
    fecha_subida = models.DateTimeField(auto_now_add=True)
    fecha_indexado = models.DateTimeField(null=True, blank=True)
    subido_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Subido por'
    )

    class Meta:
        ordering = ['-fecha_subida']
        verbose_name = 'Documento RAG Comercial'
        verbose_name_plural = 'Documentos RAG Comercial'
        unique_together = ['cliente', 'canal', 'nombre']
        indexes = [
            models.Index(fields=['cliente', 'canal', 'estado']),
        ]

    def __str__(self):
        cliente_txt = self.cliente.nombre if self.cliente else 'General'
        return f"{self.nombre} ({cliente_txt} - {self.canal})"

    @property
    def cliente_scope_id(self):
        return self.cliente_id if self.cliente_id else 0

    def indexar(self):
        """Indexa este documento en el RAG comercial (aislado de cursos)."""
        from core.rag_comercial_manager import rag_comercial_manager
        from django.utils import timezone

        if not self.archivo:
            self.estado = 'error'
            self.error_indexacion = 'Sin archivo adjunto.'
            self.save(update_fields=['estado', 'error_indexacion'])
            return 0

        if not rag_comercial_manager.disponible:
            self.estado = 'error'
            self.error_indexacion = 'ChromaDB no disponible en el servidor.'
            self.save(update_fields=['estado', 'error_indexacion'])
            return 0

        ruta_temp = None
        try:
            ruta = None
            try:
                if hasattr(self.archivo, 'path') and os.path.exists(self.archivo.path):
                    ruta = self.archivo.path
            except Exception:
                pass
            if not ruta:
                ruta_temp = self._descargar_temp()
                ruta = ruta_temp
            if not ruta:
                self.estado = 'error'
                self.error_indexacion = 'No se pudo descargar el archivo desde almacenamiento (S3).'
                self.save(update_fields=['estado', 'error_indexacion'])
                return 0

            n_chunks = rag_comercial_manager.procesar_documento(
                cliente_id=self.cliente_scope_id,
                canal=self.canal,
                ruta_archivo=ruta,
                nombre_documento=self.nombre,
                tipo=self.tipo,
            )

            if n_chunks == 0:
                from core.extractores_documento import extraer_texto_archivo

                texto_arch, metodo = extraer_texto_archivo(ruta)
                fallback = f"# {self.nombre}\n\n{(self.descripcion or '').strip()}"
                if len(fallback.strip()) < 15:
                    fallback = f"# {self.nombre}\nDocumento comercial indexado desde biblioteca RAG."
                if len(texto_arch.strip()) >= 5:
                    fallback = f"{fallback}\n\nExtracto parcial ({metodo}):\n{texto_arch[:8000]}"
                n_chunks = rag_comercial_manager.procesar_texto(
                    cliente_id=self.cliente_scope_id,
                    canal=self.canal,
                    texto=fallback,
                    nombre_documento=self.nombre,
                    tipo=self.tipo,
                )

            self.chunks_indexados = n_chunks
            if n_chunks > 0:
                self.estado = 'indexado'
                self.error_indexacion = ''
            else:
                self.estado = 'error'
                from core.extractores_documento import diagnostico_pdf
                ext = os.path.splitext(ruta)[1].lower()
                if ext == '.pdf':
                    diag = diagnostico_pdf(ruta)
                    self.error_indexacion = (
                        f'PDF sin texto indexable ({diag.get("paginas", "?")} págs, '
                        f'método={diag.get("metodo")}). '
                        'Si es escaneado, active OCR o agregue descripción al documento.'
                    )[:500]
                else:
                    self.error_indexacion = 'No se extrajo texto del archivo. Revise formato o agregue descripción.'
            self.fecha_indexado = timezone.now()
            self.save(update_fields=['chunks_indexados', 'estado', 'error_indexacion', 'fecha_indexado'])
            return n_chunks
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[DocumentoRAGComercial] Error indexando {self.nombre}: {e}")
            self.estado = 'error'
            self.error_indexacion = str(e)[:500]
            self.save(update_fields=['estado', 'error_indexacion'])
            return 0
        finally:
            if ruta_temp and os.path.exists(ruta_temp):
                try:
                    os.unlink(ruta_temp)
                except Exception:
                    pass

    def _descargar_temp(self):
        """Descarga archivo desde storage a un temporal local para indexación."""
        import tempfile

        try:
            ext = os.path.splitext(self.archivo.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                for chunk in self.archivo.chunks():
                    tmp.write(chunk)
                return tmp.name
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[DocumentoRAGComercial] Error descargando {self.nombre}: {e}")
            return None


class BibliotecaConocimiento(models.Model):
    """
    Knowledge Hub Nat — biblioteca de conocimiento agrícola por organización.
    Alimenta el RAG comercial (Chroma) además de DocumentoRAGComercial legacy.
    """

    CATEGORIA_CHOICES = [
        ('manuales', 'Manuales'),
        ('investigaciones', 'Investigaciones'),
        ('protocolos', 'Protocolos'),
        ('cartillas', 'Cartillas'),
        ('videos', 'Videos'),
        ('podcasts', 'Podcasts'),
        ('faq', 'Preguntas frecuentes'),
        ('casos', 'Casos reales'),
        ('productos', 'Productos'),
        ('normatividad', 'Normatividad'),
        ('noticias', 'Noticias'),
        ('experiencias', 'Experiencias'),
        ('general', 'General'),
    ]
    FORMATO_CHOICES = [
        ('archivo', 'Archivo (PDF, Word, Excel…)'),
        ('texto', 'Artículo / texto'),
        ('faq', 'Pregunta y respuesta'),
        ('enlace', 'Enlace web'),
        ('imagen', 'Imagen'),
        ('audio', 'Audio / podcast'),
        ('video', 'Video'),
    ]
    NIVEL_CHOICES = [
        ('basico', 'Básico'),
        ('intermedio', 'Intermedio'),
        ('avanzado', 'Avanzado'),
    ]
    FUENTE_CHOICES = [
        ('cliente', 'Organización'),
        ('agrosavia', 'AGROSAVIA'),
        ('ica', 'ICA'),
        ('fedepanela', 'Fedepanela'),
        ('cenipalma', 'Cenipalma'),
        ('ciat', 'CIAT'),
        ('fao', 'FAO'),
        ('eki', 'eki'),
        ('otro', 'Otra fuente'),
    ]
    ESTADO_PUBLICACION_CHOICES = [
        ('borrador', 'Borrador'),
        ('publicado', 'Publicado'),
        ('archivado', 'Archivado'),
    ]
    ESTADO_RAG_CHOICES = [
        ('pendiente', 'Pendiente de indexar'),
        ('indexado', 'Indexado en RAG'),
        ('error', 'Error al indexar'),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='biblioteca_conocimiento',
    )
    titulo = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, help_text='Identificador único para indexación RAG')
    categoria = models.CharField(max_length=30, choices=CATEGORIA_CHOICES, default='general')
    formato = models.CharField(max_length=20, choices=FORMATO_CHOICES, default='archivo')
    pregunta = models.CharField(max_length=500, blank=True, default='', help_text='Solo FAQ')
    texto_contenido = models.TextField(blank=True, default='', help_text='Artículo, respuesta FAQ o transcripción')
    archivo = models.FileField(
        upload_to='biblioteca_nat/%Y/%m/',
        blank=True,
        null=True,
        help_text='PDF, DOCX, TXT, XLSX, imagen, audio o video',
    )
    enlace_url = models.URLField(max_length=500, blank=True, default='')
    cultivo = models.CharField(max_length=80, blank=True, default='')
    problema = models.CharField(max_length=120, blank=True, default='')
    region = models.CharField(max_length=120, blank=True, default='')
    idioma = models.CharField(max_length=20, default='es', verbose_name='Idioma')
    nivel = models.CharField(max_length=20, choices=NIVEL_CHOICES, default='basico')
    fuente = models.CharField(max_length=30, choices=FUENTE_CHOICES, default='cliente')
    autor = models.CharField(max_length=120, blank=True, default='')
    fecha_contenido = models.DateField(null=True, blank=True)
    estado_publicacion = models.CharField(
        max_length=20,
        choices=ESTADO_PUBLICACION_CHOICES,
        default='publicado',
    )
    estado_rag = models.CharField(max_length=20, choices=ESTADO_RAG_CHOICES, default='pendiente')
    rag_error_detalle = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='Motivo del último fallo de indexación (si aplica).',
    )
    chunks_indexados = models.IntegerField(default=0)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_indexado = models.DateTimeField(null=True, blank=True)
    subido_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='biblioteca_subidos',
    )

    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = 'Conocimiento (biblioteca Nat)'
        verbose_name_plural = 'Biblioteca de conocimiento Nat'
        unique_together = [('cliente', 'slug')]
        indexes = [
            models.Index(fields=['cliente', 'estado_publicacion', 'categoria']),
        ]

    def __str__(self):
        return f'{self.titulo} ({self.cliente.nombre})'

    @property
    def cliente_scope_id(self):
        return self.cliente_id


class ProductoComercial(models.Model):
    """
    Catálogo de precios estructurado para Nat (WhatsApp comercial).
    Fuente de verdad en Postgres; el RAG comercial queda para documentos técnicos.
    """

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='productos_comerciales',
        verbose_name='Cliente',
        help_text='Vacío = catálogo general visible para todos los clientes.',
    )
    sku = models.CharField(
        max_length=80,
        verbose_name='SKU / código',
        help_text='Identificador único por cliente (ej: UREA-46-50KG).',
    )
    nombre = models.CharField(max_length=200, verbose_name='Nombre del producto')
    presentacion = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name='Presentación',
        help_text='Ej: bulto 50 kg, garrafa 1 L.',
    )
    unidad = models.CharField(
        max_length=40,
        blank=True,
        default='',
        verbose_name='Unidad de venta',
        help_text='Ej: bulto, kg, litro.',
    )
    stock = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Stock disponible',
        help_text='Unidades en bodega (opcional). Vacío = no se reporta inventario.',
    )
    precio = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name='Precio',
    )
    moneda = models.CharField(max_length=8, default='COP', verbose_name='Moneda')
    categoria = models.CharField(
        max_length=80,
        blank=True,
        default='',
        verbose_name='Categoría',
        help_text='Ej: fertilizante, herbicida, fungicida.',
    )
    notas = models.TextField(blank=True, default='', verbose_name='Notas comerciales')
    vigencia_desde = models.DateField(null=True, blank=True, verbose_name='Vigente desde')
    vigencia_hasta = models.DateField(null=True, blank=True, verbose_name='Vigente hasta')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Producto comercial (precio)'
        verbose_name_plural = 'Productos comerciales (precios)'
        ordering = ['nombre', 'sku']
        constraints = [
            models.UniqueConstraint(
                fields=['cliente', 'sku'],
                name='uniq_producto_comercial_cliente_sku',
            ),
        ]
        indexes = [
            models.Index(fields=['cliente', 'activo', '-fecha_actualizacion']),
            models.Index(fields=['nombre']),
            models.Index(fields=['categoria']),
        ]

    def __str__(self):
        cliente_txt = self.cliente.nombre if self.cliente_id else 'General'
        return f"{self.sku} — {self.nombre} ({cliente_txt})"


class ProductoCatalogo(models.Model):
    """
    Catálogo comercial por organización (Cliente) para recomendaciones Nat.
    Separado de ProductoComercial (lista de precios SKU) y de DocumentoRAGComercial.
    """

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='catalogo_productos',
        verbose_name='Cliente',
    )
    nombre = models.CharField(max_length=200, verbose_name='Nombre del producto')
    sku = models.CharField(
        max_length=80,
        blank=True,
        default='',
        verbose_name='SKU / código',
        help_text='Opcional. Si coincide con un SKU de Precios, Nat une ficha + precio + stock.',
    )
    imagen = models.ImageField(
        upload_to='nat/productos/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='Foto del producto',
        help_text='Imagen del empaque o presentación (JPG/PNG/WebP). Se guarda en S3 en producción.',
    )
    descripcion = models.TextField(
        verbose_name='Descripción',
        help_text='Para qué sirve el producto',
    )
    problema_que_resuelve = models.TextField(
        verbose_name='Problemas que resuelve',
        help_text=(
            'Síntomas o problemas del cultivo que este producto atiende. '
            'Ej: roya, manchas amarillas, deficiencia de nitrógeno, plagas de suelo. '
            'Mientras más descriptivo, mejor el match con la pregunta del agricultor.'
        ),
    )
    ingrediente_activo = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Ingrediente activo',
    )
    categoria = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Categoría',
        help_text='Ej: fungicida, fertilizante foliar, bioestimulante, herbicida',
    )
    cultivos_objetivo = models.CharField(
        max_length=300,
        blank=True,
        verbose_name='Cultivos objetivo',
        help_text='Ej: café, caña panelera, aguacate, maíz',
    )
    dosis = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Dosis recomendada',
        help_text='Ej: 300-500g por 200L de agua',
    )
    precio_cop = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name='Precio (COP)',
    )
    unidad = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Unidad de venta',
        help_text='Ej: 500g, 1L, bolsa x 25kg',
    )
    url_producto = models.URLField(
        blank=True,
        verbose_name='Link del producto',
        help_text='URL directa a la página de compra del producto',
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Producto del catálogo'
        verbose_name_plural = 'Catálogo de productos'
        ordering = ['cliente', 'categoria', 'nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['cliente', 'nombre'],
                name='uniq_producto_catalogo_cliente_nombre',
            ),
        ]

    def __str__(self):
        precio_str = f' — ${self.precio_cop:,.0f}' if self.precio_cop else ''
        return f'{self.nombre} ({self.cliente.nombre}){precio_str}'
