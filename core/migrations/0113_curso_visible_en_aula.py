from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0112_modulo_contenido_opcional_con_pasos'),
    ]

    operations = [
        migrations.AddField(
            model_name='curso',
            name='visible_en_aula',
            field=models.BooleanField(
                default=True,
                help_text=(
                    'Si está activo, el curso aparece en el catálogo de /aprende/ para que '
                    'los estudiantes lo elijan. El contenido subido por profesores queda '
                    'disponible para quienes se inscriban.'
                ),
                verbose_name='Visible en aula web',
            ),
        ),
    ]
