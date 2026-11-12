from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0206_plantilla_layout_stickers'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plantillacertificado',
            name='texto_superior',
            field=models.CharField(
                default='eki',
                help_text=(
                    "Texto en la parte superior. Vacío o el legado "
                    "'eki - Soluciones Educativas' se pinta solo como eki."
                ),
                max_length=200,
            ),
        ),
    ]
