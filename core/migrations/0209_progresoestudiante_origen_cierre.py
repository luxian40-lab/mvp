from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0208_curso_version'),
    ]

    operations = [
        migrations.AddField(
            model_name='progresoestudiante',
            name='origen_cierre',
            field=models.CharField(
                blank=True,
                choices=[
                    ('chat', 'Chat'),
                    ('operacion', 'Operación'),
                    ('presencial', 'Presencial'),
                ],
                help_text='Cómo se cerró el curso: chat, operación o presencial. Vacío en cierres previos.',
                max_length=16,
                null=True,
                verbose_name='Origen del cierre',
            ),
        ),
    ]
