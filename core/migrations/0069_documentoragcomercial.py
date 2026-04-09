from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0068_alter_preguntaabiertafinalcurso_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentoRAGComercial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('canal', models.CharField(choices=[('bot_comercial', 'Bot Comercial WhatsApp')], default='bot_comercial', max_length=40, verbose_name='Canal comercial')),
                ('nombre', models.CharField(help_text='Identificador único por cliente/canal (ej: catalogo_abril_2026).', max_length=200, verbose_name='Nombre del documento')),
                ('archivo', models.FileField(help_text='Formatos soportados: .pdf, .docx, .txt', upload_to='documentos_rag_comercial/%Y/%m/', verbose_name='Archivo (PDF, DOCX, TXT)')),
                ('tipo', models.CharField(choices=[('producto', 'Producto / Catálogo'), ('precio', 'Precio / Lista comercial'), ('faq', 'Preguntas frecuentes comerciales'), ('politica', 'Políticas comerciales'), ('promo', 'Promociones'), ('general', 'Información general comercial')], default='producto', max_length=20, verbose_name='Tipo de documento')),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente de indexar'), ('indexado', 'Indexado en RAG comercial'), ('error', 'Error al indexar')], default='pendiente', max_length=20, verbose_name='Estado RAG')),
                ('chunks_indexados', models.IntegerField(default=0, help_text='Cantidad de fragmentos indexados en la BD vectorial comercial.', verbose_name='Chunks indexados')),
                ('descripcion', models.TextField(blank=True, help_text='Descripción opcional del contenido comercial.', verbose_name='Descripción')),
                ('fecha_subida', models.DateTimeField(auto_now_add=True)),
                ('fecha_indexado', models.DateTimeField(blank=True, null=True)),
                ('cliente', models.ForeignKey(blank=True, help_text='Cliente comercial del documento. Vacío = comercial general.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='documentos_rag_comercial', to='core.cliente', verbose_name='Cliente')),
                ('subido_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user', verbose_name='Subido por')),
            ],
            options={
                'verbose_name': 'Documento RAG Comercial',
                'verbose_name_plural': 'Documentos RAG Comercial',
                'ordering': ['-fecha_subida'],
                'unique_together': {('cliente', 'canal', 'nombre')},
            },
        ),
        migrations.AddIndex(
            model_name='documentoragcomercial',
            index=models.Index(fields=['cliente', 'canal', 'estado'], name='core_docume_cliente_a7a17d_idx'),
        ),
    ]
