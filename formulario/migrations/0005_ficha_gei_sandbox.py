# Generated manually for GEI sandbox slots

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('formulario', '0004_gei_formulas_v2'),
    ]

    operations = [
        migrations.AddField(
            model_name='fichagei',
            name='es_sandbox',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='Ficha de ensayo en portal: no mezcla con inventario operativo.',
                verbose_name='Sandbox (prueba)',
            ),
        ),
        migrations.AddField(
            model_name='fichagei',
            name='referencia_balance_tco2e',
            field=models.FloatField(
                blank=True,
                help_text='Valor esperado para comparar y medir margen de error en sandbox.',
                null=True,
                verbose_name='Referencia balance (t CO₂e/año)',
            ),
        ),
    ]
