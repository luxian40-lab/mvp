import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0113_curso_visible_en_aula'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TareaCurso',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=200)),
                ('instrucciones', models.TextField(blank=True)),
                ('fecha_limite', models.DateTimeField(blank=True, null=True)),
                ('activa', models.BooleanField(default=True)),
                ('orden', models.IntegerField(default=0)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('curso', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tareas_aula', to='core.curso')),
                ('modulo', models.ForeignKey(blank=True, help_text='Opcional: vincular la tarea a una lección específica.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tareas_aula', to='core.modulo')),
            ],
            options={
                'verbose_name': 'Tarea del curso',
                'verbose_name_plural': 'Tareas del curso',
                'ordering': ['orden', '-fecha_creacion'],
            },
        ),
        migrations.CreateModel(
            name='EntregaTarea',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('archivo', models.FileField(upload_to='aprende/entregas/%Y/%m/')),
                ('nombre_archivo', models.CharField(blank=True, max_length=255)),
                ('comentario_estudiante', models.TextField(blank=True)),
                ('fecha_entrega', models.DateTimeField(auto_now=True)),
                ('nota', models.IntegerField(blank=True, help_text='Calificación del profesor (1 a 5).', null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('comentario_profesor', models.TextField(blank=True)),
                ('fecha_calificacion', models.DateTimeField(blank=True, null=True)),
                ('calificado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='entregas_calificadas', to=settings.AUTH_USER_MODEL)),
                ('estudiante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='entregas_tareas', to='core.estudiante')),
                ('tarea', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='entregas', to='aprende.tareacurso')),
            ],
            options={
                'verbose_name': 'Entrega de tarea',
                'verbose_name_plural': 'Entregas de tareas',
                'ordering': ['-fecha_entrega'],
                'unique_together': {('tarea', 'estudiante')},
            },
        ),
    ]
