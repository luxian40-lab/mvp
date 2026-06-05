from django.db import migrations, models


def poblar_modo_desde_boolean(apps, schema_editor):
    Cliente = apps.get_model('core', 'Cliente')
    for c in Cliente.objects.all().only('pk', 'usar_gamificacion', 'modo_gamificacion'):
        if c.usar_gamificacion:
            c.modo_gamificacion = 'puntos'
        else:
            c.modo_gamificacion = 'desactivado'
        c.save(update_fields=['modo_gamificacion'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0102_cliente_portal_productos'),
    ]

    operations = [
        migrations.AddField(
            model_name='cliente',
            name='modo_gamificacion',
            field=models.CharField(
                choices=[
                    ('desactivado', 'Desactivada'),
                    ('puntos', 'Puntos (ranking y recompensas)'),
                    ('calificacion', 'Calificación 1–5 (facilitadora)'),
                ],
                default='puntos',
                help_text=(
                    'Puntos: ranking y suma de puntos al evaluar retos (comportamiento actual). '
                    'Calificación 1–5: la facilitadora califica con notas decimales (ej. 3,5); no suma puntos. '
                    'Desactivada: sin gamificación visible.'
                ),
                max_length=20,
                verbose_name='Modo de gamificación',
            ),
        ),
        migrations.RunPython(poblar_modo_desde_boolean, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='cliente',
            name='usar_gamificacion',
            field=models.BooleanField(
                default=True,
                help_text='Sincronizado automáticamente desde «Modo de gamificación». Legacy para compatibilidad.',
                verbose_name='Usar Gamificación',
            ),
        ),
    ]
