from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0115_curso_visible_en_studio'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('aprende', '0002_estudiante_foto_perfil'),
    ]

    operations = [
        migrations.CreateModel(
            name='AsistenciaAula',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField(verbose_name='Fecha de sesión')),
                ('presente', models.BooleanField(default=True)),
                ('fecha_registro', models.DateTimeField(auto_now=True)),
                ('curso', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='asistencias_aula', to='core.curso')),
                ('estudiante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='asistencias_aula', to='core.estudiante')),
                ('registrado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='asistencias_registradas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Asistencia (aula)',
                'verbose_name_plural': 'Asistencias (aula)',
                'ordering': ['-fecha', 'estudiante__nombre'],
                'unique_together': {('curso', 'estudiante', 'fecha')},
            },
        ),
    ]
