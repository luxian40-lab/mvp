from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0187_cursos_linea_2_global'),
    ]

    operations = [
        migrations.AddField(
            model_name='sandboxcanalsesion',
            name='phone_id',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Phone number id de la línea. Vacío = sesión anterior a las dos líneas.',
                max_length=32,
                verbose_name='Línea Meta',
            ),
        ),
        migrations.AlterField(
            model_name='sandboxcanalsesion',
            name='telefono',
            field=models.CharField(db_index=True, max_length=30),
        ),
        migrations.AddConstraint(
            model_name='sandboxcanalsesion',
            constraint=models.UniqueConstraint(
                fields=('telefono', 'phone_id'),
                name='uniq_sandbox_sesion_tel_linea',
            ),
        ),
        migrations.AddField(
            model_name='whatsapplog',
            name='phone_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text='Phone number id de la línea por la que salió o entró. Vacío en el histórico.',
                max_length=32,
                verbose_name='Línea Meta',
            ),
        ),
    ]
