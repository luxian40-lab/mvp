# Generated manually for rol profesor (choices only)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='portalusuario',
            name='rol',
            field=models.CharField(
                choices=[
                    ('admin', 'Administrador'),
                    ('profesor', 'Profesor (aula web)'),
                    ('viewer', 'Solo lectura'),
                ],
                default='viewer',
                max_length=20,
            ),
        ),
    ]
