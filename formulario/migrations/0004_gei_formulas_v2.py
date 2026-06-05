# Generated manually for GEI formula update

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("formulario", "0003_resultadogei"),
    ]

    operations = [
        migrations.AddField(
            model_name="fichagei",
            name="tipo_fertilizante",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "—"),
                    ("sintetico", "Síntesis química (con % N en empaque)"),
                    ("organico", "Orgánico sin composición fija (compost, abono)"),
                ],
                default="",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="fichagei",
            name="tipo_cultivo",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "—"),
                    ("perenne", "Perenne (café, cacao, plátano…)"),
                    ("transitorio", "Transitorio (maíz, papa, hortalizas…)"),
                    ("arroz", "Arroz en inundación"),
                ],
                default="",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="fichagei",
            name="alta_mecanizacion",
            field=models.BooleanField(blank=True, null=True, verbose_name="¿Alta mecanización?"),
        ),
        migrations.AddField(
            model_name="fichagei",
            name="usa_enmiendas_cal",
            field=models.BooleanField(blank=True, null=True, verbose_name="¿Usa enmiendas como cal?"),
        ),
        migrations.AddField(
            model_name="fichagei",
            name="anio_datos_energia",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="2025 → factor 0.097; 2026 o posterior → 0.126 kg CO₂e/kWh",
                null=True,
                verbose_name="Año de referencia energía",
            ),
        ),
        migrations.AlterField(
            model_name="fichagei",
            name="manejo_residuos",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "—"),
                    ("compost", "Compostaje"),
                    ("suelo_directo", "Disposición directa en suelo"),
                    ("externo", "Entrega a tercero / recolección"),
                    ("quemado", "Quema en campo (no recomendado)"),
                    ("otro", "Otra forma / no aplica"),
                ],
                default="",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="resultadogei",
            name="nota_cobertura",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="Nota de cobertura metodológica",
            ),
        ),
    ]
