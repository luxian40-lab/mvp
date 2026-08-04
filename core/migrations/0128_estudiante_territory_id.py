# Generated manually for territory_id DIVIPOLA on Estudiante

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0127_estudiante_documento_latam'),
    ]

    operations = [
        migrations.AddField(
            model_name='estudiante',
            name='territory_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text='Código DIVIPOLA de 5 dígitos del municipio canónico. Vacío si no resuelto.',
                max_length=10,
                verbose_name='Territory ID (DIVIPOLA)',
            ),
        ),
    ]
