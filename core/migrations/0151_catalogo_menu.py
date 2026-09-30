from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0150_plantilla_campana_meta'),
    ]

    operations = [
        migrations.AddField(
            model_name='curso',
            name='catalogo_menu',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Curso sin cliente, visible para cualquier estudiante. '
                    'Aparece en el carrusel de Formación del menú.'
                ),
                verbose_name='Catálogo general del menú',
            ),
        ),
    ]
