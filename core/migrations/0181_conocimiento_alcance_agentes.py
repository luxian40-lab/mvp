from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0180_campana_meta_inicio_flujo'),
    ]

    operations = [
        migrations.AddField(
            model_name='conocimientoagente',
            name='alcance',
            field=models.CharField(
                choices=[('todos', 'Todos'), ('cliente', 'Un cliente')],
                default='todos',
                max_length=16,
                verbose_name='Alcance',
            ),
        ),
        migrations.AddField(
            model_name='conocimientoagente',
            name='cliente',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='conocimientos_agente',
                to='core.cliente',
                verbose_name='Cliente',
            ),
        ),
        migrations.AddField(
            model_name='conversacionragcandidata',
            name='agentes',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Agentes que pueden usar esta respuesta.',
                verbose_name='Aplica a',
            ),
        ),
        migrations.AddField(
            model_name='conversacionragcandidata',
            name='alcance',
            field=models.CharField(
                choices=[('todos', 'Todos'), ('cliente', 'Un cliente')],
                default='todos',
                max_length=16,
                verbose_name='Alcance',
            ),
        ),
    ]
