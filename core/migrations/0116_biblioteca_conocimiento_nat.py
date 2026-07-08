from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0115_curso_visible_en_studio'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BibliotecaConocimiento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=200)),
                ('slug', models.SlugField(help_text='Identificador único para indexación RAG', max_length=200)),
                ('categoria', models.CharField(choices=[('manuales', 'Manuales'), ('investigaciones', 'Investigaciones'), ('protocolos', 'Protocolos'), ('cartillas', 'Cartillas'), ('videos', 'Videos'), ('podcasts', 'Podcasts'), ('faq', 'Preguntas frecuentes'), ('casos', 'Casos reales'), ('productos', 'Productos'), ('normatividad', 'Normatividad'), ('noticias', 'Noticias'), ('experiencias', 'Experiencias'), ('general', 'General')], default='general', max_length=30)),
                ('formato', models.CharField(choices=[('archivo', 'Archivo (PDF, Word, Excel…)'), ('texto', 'Artículo / texto'), ('faq', 'Pregunta y respuesta'), ('enlace', 'Enlace web'), ('imagen', 'Imagen'), ('audio', 'Audio / podcast'), ('video', 'Video')], default='archivo', max_length=20)),
                ('pregunta', models.CharField(blank=True, default='', help_text='Solo FAQ', max_length=500)),
                ('texto_contenido', models.TextField(blank=True, default='', help_text='Artículo, respuesta FAQ o transcripción')),
                ('archivo', models.FileField(blank=True, help_text='PDF, DOCX, TXT, XLSX, imagen, audio o video', null=True, upload_to='biblioteca_nat/%Y/%m/')),
                ('enlace_url', models.URLField(blank=True, default='', max_length=500)),
                ('cultivo', models.CharField(blank=True, default='', max_length=80)),
                ('problema', models.CharField(blank=True, default='', max_length=120)),
                ('region', models.CharField(blank=True, default='', max_length=120)),
                ('idioma', models.CharField(default='es', max_length=20, verbose_name='Idioma')),
                ('nivel', models.CharField(choices=[('basico', 'Básico'), ('intermedio', 'Intermedio'), ('avanzado', 'Avanzado')], default='basico', max_length=20)),
                ('fuente', models.CharField(choices=[('cliente', 'Organización'), ('agrosavia', 'AGROSAVIA'), ('ica', 'ICA'), ('fedepanela', 'Fedepanela'), ('cenipalma', 'Cenipalma'), ('ciat', 'CIAT'), ('fao', 'FAO'), ('eki', 'eki'), ('otro', 'Otra fuente')], default='cliente', max_length=30)),
                ('autor', models.CharField(blank=True, default='', max_length=120)),
                ('fecha_contenido', models.DateField(blank=True, null=True)),
                ('estado_publicacion', models.CharField(choices=[('borrador', 'Borrador'), ('publicado', 'Publicado'), ('archivado', 'Archivado')], default='publicado', max_length=20)),
                ('estado_rag', models.CharField(choices=[('pendiente', 'Pendiente de indexar'), ('indexado', 'Indexado en RAG'), ('error', 'Error al indexar')], default='pendiente', max_length=20)),
                ('chunks_indexados', models.IntegerField(default=0)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_indexado', models.DateTimeField(blank=True, null=True)),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='biblioteca_conocimiento', to='core.cliente')),
                ('subido_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='biblioteca_subidos', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Conocimiento (biblioteca Nat)',
                'verbose_name_plural': 'Biblioteca de conocimiento Nat',
                'ordering': ['-fecha_creacion'],
                'unique_together': {('cliente', 'slug')},
            },
        ),
        migrations.AddIndex(
            model_name='bibliotecaconocimiento',
            index=models.Index(fields=['cliente', 'estado_publicacion', 'categoria'], name='core_biblio_cliente_cat_idx'),
        ),
    ]
