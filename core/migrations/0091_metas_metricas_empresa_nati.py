# Generated manually for MetaMetricaEmpresa / MetaMetricaNati

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0090_habilitacion_modulo_calendario_drip"),
    ]

    operations = [
        migrations.CreateModel(
            name="MetaMetricaEmpresa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("meta_finalizacion_porcentaje", models.DecimalField(decimal_places=2, default=70, max_digits=5)),
                ("meta_inicio_porcentaje", models.DecimalField(decimal_places=2, default=80, max_digits=5)),
                ("meta_max_no_iniciados_porcentaje", models.DecimalField(decimal_places=2, default=20, max_digits=5)),
                ("meta_min_lectura_mensajes_porcentaje", models.DecimalField(decimal_places=2, default=60, max_digits=5)),
                ("verde_desde", models.DecimalField(decimal_places=2, default=80, max_digits=5)),
                ("amarillo_desde", models.DecimalField(decimal_places=2, default=50, max_digits=5)),
                ("activa", models.BooleanField(default=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                (
                    "cliente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="metas_metricas",
                        to="core.cliente",
                        verbose_name="Organización",
                    ),
                ),
                (
                    "curso",
                    models.ForeignKey(
                        blank=True,
                        help_text="Vacío = meta general del cliente para todos los cursos.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="metas_metricas",
                        to="core.curso",
                        verbose_name="Curso",
                    ),
                ),
            ],
            options={
                "verbose_name": "Meta métrica empresa",
                "verbose_name_plural": "Metas métricas por empresa",
            },
        ),
        migrations.CreateModel(
            name="MetaMetricaNati",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("meta_lectura_porcentaje", models.DecimalField(decimal_places=2, default=60, max_digits=5, verbose_name="Meta lectura WhatsApp (%)")),
                ("meta_respuesta_porcentaje", models.DecimalField(decimal_places=2, default=70, max_digits=5, verbose_name="Meta respuesta a consultas (%)")),
                ("verde_desde", models.DecimalField(decimal_places=2, default=80, max_digits=5)),
                ("amarillo_desde", models.DecimalField(decimal_places=2, default=50, max_digits=5)),
                ("activa", models.BooleanField(default=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                (
                    "cliente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="metas_nati",
                        to="core.cliente",
                        verbose_name="Organización",
                    ),
                ),
            ],
            options={
                "verbose_name": "Meta métrica Nati",
                "verbose_name_plural": "Metas métricas Nati",
            },
        ),
        migrations.AddConstraint(
            model_name="metametricaempresa",
            constraint=models.UniqueConstraint(
                condition=models.Q(("curso__isnull", False)),
                fields=("cliente", "curso"),
                name="uniq_meta_metrica_cliente_curso",
            ),
        ),
        migrations.AddConstraint(
            model_name="metametricaempresa",
            constraint=models.UniqueConstraint(
                condition=models.Q(("curso__isnull", True)),
                fields=("cliente",),
                name="uniq_meta_metrica_cliente_general",
            ),
        ),
    ]
