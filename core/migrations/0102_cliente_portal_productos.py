from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0101_cliente_portal_branding'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='portal_productos',
            field=models.CharField(
                blank=True,
                default='',
                help_text=(
                    'Módulos visibles en el portal B2B, separados por coma: cursos, gei, nat. '
                    'Ej: cursos,gei para cooperativa con formación y fichas. '
                    'Vacío = solo el tipo de producto principal.'
                ),
                max_length=100,
                verbose_name='Módulos del portal',
            ),
        ),
    ]
