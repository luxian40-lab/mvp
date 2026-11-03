from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0199_nota_cierre_curso'),
    ]

    operations = [
        migrations.AddField(
            model_name='recordatoriocurso',
            name='maximo_envios',
            field=models.PositiveSmallIntegerField(
                default=3,
                help_text=(
                    'Tope de recordatorios enviados desde la última señal (mensaje o aviso). '
                    'Si escribe de nuevo, la cuenta vuelve a cero.'
                ),
                verbose_name='Máximo de envíos',
            ),
        ),
        migrations.AlterField(
            model_name='recordatoriocurso',
            name='repetir_cada_dias',
            field=models.PositiveSmallIntegerField(
                default=7,
                help_text='Si sigue sin avanzar, otro recordatorio cada tantos días.',
                verbose_name='Repetir cada (días)',
            ),
        ),
    ]
