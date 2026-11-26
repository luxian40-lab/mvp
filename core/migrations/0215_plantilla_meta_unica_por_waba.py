from django.db import migrations, models


class Migration(migrations.Migration):
    """La misma plantilla puede vivir en dos WABA (línea 1 y línea 3)."""

    dependencies = [
        ('core', '0214_recordatorio_curso_activo_hasta'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='plantillameta',
            name='uniq_plantilla_meta_nombre_idioma',
        ),
        migrations.AddConstraint(
            model_name='plantillameta',
            constraint=models.UniqueConstraint(
                fields=['meta_name', 'idioma', 'waba_id'],
                name='uniq_plantilla_meta_nombre_idioma_waba',
            ),
        ),
    ]
