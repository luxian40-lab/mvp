import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0150_plantilla_campana_meta'),
    ]

    operations = [
        migrations.CreateModel(
            name='VideoEnlace',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(db_index=True, max_length=40, unique=True)),
                ('video_id', models.CharField(db_index=True, max_length=64)),
                ('etiqueta', models.CharField(blank=True, default='', max_length=200)),
                ('destino_tipo', models.CharField(choices=[('s3', 'S3 (URL firmada al abrir)'), ('archivo', 'Archivo directo (reproductor propio)'), ('externo', 'YouTube o Vimeo (redirect)')], max_length=16)),
                ('destino_ref', models.TextField(help_text='Key S3 o URL de YouTube/Vimeo/archivo. Nunca una URL ya firmada.')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('curso', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enlaces_video', to='core.curso')),
                ('estudiante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enlaces_video', to='core.estudiante')),
                ('modulo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='enlaces_video', to='core.modulo')),
            ],
            options={
                'verbose_name': 'Enlace de video',
                'verbose_name_plural': 'Enlaces de video',
            },
        ),
        migrations.CreateModel(
            name='VideoView',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('video_id', models.CharField(db_index=True, max_length=64)),
                ('evento', models.CharField(choices=[('apertura', 'Apertura del enlace'), ('progreso_25', 'Progreso 25%'), ('progreso_50', 'Progreso 50%'), ('progreso_75', 'Progreso 75%'), ('progreso_100', 'Progreso 100%')], db_index=True, max_length=20)),
                ('user_agent', models.CharField(blank=True, default='', max_length=400)),
                ('creado_en', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('curso', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vistas_video', to='core.curso')),
                ('enlace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vistas', to='core.videoenlace')),
                ('estudiante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vistas_video', to='core.estudiante')),
                ('modulo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='vistas_video', to='core.modulo')),
            ],
            options={
                'verbose_name': 'Vista de video',
                'verbose_name_plural': 'Vistas de video',
                'ordering': ['-creado_en'],
            },
        ),
        migrations.AddConstraint(
            model_name='videoenlace',
            constraint=models.UniqueConstraint(fields=('estudiante', 'video_id'), name='uniq_video_enlace_estudiante_video'),
        ),
        migrations.AddIndex(
            model_name='videoview',
            index=models.Index(fields=['curso', 'evento', 'creado_en'], name='core_videov_curso_i_dbcc4c_idx'),
        ),
        migrations.AddIndex(
            model_name='videoview',
            index=models.Index(fields=['estudiante', 'video_id', 'evento'], name='core_videov_estudia_e29911_idx'),
        ),
        migrations.AddIndex(
            model_name='videoview',
            index=models.Index(fields=['enlace', 'evento'], name='core_videov_enlace__96996c_idx'),
        ),
    ]
