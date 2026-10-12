from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0178_merge_campana_y_plantilla_media'),
    ]

    operations = [
        migrations.AddField(
            model_name='campanameta',
            name='es_inicio_flujo',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Sí: al enviarla, la próxima respuesta entra por el habeas data y sigue el menú. '
                    'No: es un recordatorio. La respuesta continúa en lo que la persona ya llevaba.'
                ),
                verbose_name='Inicio de flujo',
            ),
        ),
    ]
