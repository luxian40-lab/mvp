# Generated manually: modo ventas en menú sandbox

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0146_documentorag_uso_agente'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sandboxcanalsesion',
            name='modo',
            field=models.CharField(
                choices=[
                    ('menu', 'Menú'),
                    ('agentes', 'Submenú agentes'),
                    ('nat', 'Agrónomo (Nat)'),
                    ('coach', 'Coach'),
                    ('ia_campo', 'IA para el campo'),
                    ('ventas', 'Ventas y comercialización'),
                    ('cursos', 'Cursos'),
                ],
                default='menu',
                max_length=16,
            ),
        ),
    ]
