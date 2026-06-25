from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0111_portal_feedback_gei_factores'),
    ]

    operations = [
        migrations.AlterField(
            model_name='modulo',
            name='contenido',
            field=models.TextField(
                blank=True,
                default='',
                help_text=(
                    'Contenido educativo del módulo completo. Obligatorio si no hay microcontenidos; '
                    'opcional si configuró pasos en la pestaña Microcontenidos.'
                ),
            ),
        ),
    ]
