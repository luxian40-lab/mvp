# PQRS: máximo 2 preguntas de clarificación por ticket

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0093_contexto_agro_hitl'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitudsoporte',
            name='preguntas_realizadas',
            field=models.IntegerField(
                default=0,
                verbose_name='Preguntas de clarificación',
                help_text='Contador de preguntas de clarificación del agente PQRS (máximo 2).',
            ),
        ),
    ]
