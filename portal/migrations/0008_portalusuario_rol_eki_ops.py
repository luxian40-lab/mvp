# Generated manually — rol eki_ops para semi-admin en app

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0007_profesor_aula_proxy'),
    ]

    operations = [
        migrations.AlterField(
            model_name='portalusuario',
            name='rol',
            field=models.CharField(
                choices=[
                    ('admin', 'Administrador (portal clientes)'),
                    ('profesor', 'Profesor (solo aula web /aprende/)'),
                    ('viewer', 'Solo lectura (portal clientes)'),
                    ('eki_ops', 'Equipo eki (ops)'),
                ],
                default='viewer',
                max_length=20,
            ),
        ),
    ]
