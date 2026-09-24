from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0147_sandbox_modo_ventas'),
    ]

    operations = [
        migrations.AddField(
            model_name='sandboxcanalsesion',
            name='habeas_aceptado',
            field=models.BooleanField(
                default=False,
                help_text='Aceptó tratamiento de datos en la línea Meta antes del menú.',
            ),
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
                    ('ventas', 'Ventas y comercialización'),
                    ('cursos', 'Cursos'),
                    ('formacion', 'Formación'),
                    ('asesoria', 'Asesoría'),
                ],
                default='menu',
                max_length=16,
            ),
        ),
    ]
