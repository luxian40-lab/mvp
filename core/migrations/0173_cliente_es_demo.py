from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0172_nota_estudiante'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='es_demo',
            field=models.BooleanField(
                default=False,
                help_text='Marca organizaciones de prueba. No cambia envíos ni permisos.',
                verbose_name='Es demo o prueba',
            ),
        ),
    ]
