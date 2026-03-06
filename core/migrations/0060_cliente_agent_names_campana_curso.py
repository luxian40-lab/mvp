# Generated manually - Django 5.2.9

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0059_update_cert_paths'),
    ]

    operations = [
        # Agent names on Cliente model (take priority over Curso)
        migrations.AddField(
            model_name='cliente',
            name='nombre_agente_tutor',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Nombre del agente tutor IA (aplica a TODOS los cursos del cliente)',
                max_length=100,
                verbose_name='Nombre Agente Tutor',
            ),
        ),
        migrations.AddField(
            model_name='cliente',
            name='nombre_agente_asistente',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Nombre del agente asistente IA (aplica a TODOS los cursos del cliente)',
                max_length=100,
                verbose_name='Nombre Agente Asistente',
            ),
        ),
        # Campaign course start fields
        migrations.AddField(
            model_name='campana',
            name='es_campana_curso',
            field=models.BooleanField(
                default=False,
                help_text='Si es True, al enviar la campaña se reinicia el onboarding del estudiante para que inicie el curso',
                verbose_name='¿Es campaña de inicio de curso?',
            ),
        ),
        migrations.AddField(
            model_name='campana',
            name='curso_destino',
            field=models.ForeignKey(
                blank=True,
                help_text='Curso al que se inscribirá el estudiante al iniciar la campaña',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='campanas_curso',
                to='core.curso',
                verbose_name='Curso destino',
            ),
        ),
    ]
