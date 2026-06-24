from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0108_enlace_formulario_externo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enlaceformularioexterno',
            name='campo_identificador',
            field=models.CharField(
                choices=[
                    ('cedula', 'Solo cédula (menos seguro)'),
                    ('telefono', 'Solo teléfono WhatsApp'),
                    ('cedula_y_telefono', 'Cédula + teléfono (recomendado)'),
                    ('cedula_y_nombre', 'Cédula + nombre completo'),
                ],
                default='cedula_y_telefono',
                max_length=24,
                verbose_name='Validación de identidad',
            ),
        ),
    ]
