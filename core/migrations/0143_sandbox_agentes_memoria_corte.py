# Generated manually for sandbox agentes + Nat memory cut

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0142_sandbox_menu_event_engine_lake'),
    ]

    operations = [
        migrations.AddField(
            model_name='sandboxcanalsesion',
            name='memoria_corte_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
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
                    ('cursos', 'Cursos'),
                ],
                default='menu',
                max_length=16,
            ),
        ),
    ]
