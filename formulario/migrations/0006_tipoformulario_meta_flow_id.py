from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('formulario', '0005_ficha_gei_sandbox'),
    ]

    operations = [
        migrations.AddField(
            model_name='tipoformulario',
            name='meta_flow_id',
            field=models.CharField(
                blank=True,
                default='',
                help_text=(
                    'Si está vacío, la línea Meta lo publica sola a partir de los pasos. '
                    'Si WhatsApp no lo abre, las preguntas siguen una por una en el chat.'
                ),
                max_length=40,
                verbose_name='Formulario WhatsApp (Flow)',
            ),
        ),
    ]
