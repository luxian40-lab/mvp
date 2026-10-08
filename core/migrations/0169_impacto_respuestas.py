from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0168_impacto_ficha'),
    ]

    operations = [
        migrations.AddField(
            model_name='estudiante',
            name='impacto_respuestas',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Captura B por código (E1, E2, A1, A3). No se inventa el dato.',
                verbose_name='Respuestas de impacto (agentes)',
            ),
        ),
    ]
