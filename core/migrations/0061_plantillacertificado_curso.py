# Generated manually - Django 5.2.9

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0060_cliente_agent_names_campana_curso'),
    ]

    operations = [
        migrations.AddField(
            model_name='plantillacertificado',
            name='curso',
            field=models.ForeignKey(
                blank=True,
                help_text='Curso específico para esta plantilla. Si se asigna, se usará automáticamente al completar este curso.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='plantillas_certificados',
                to='core.curso',
                verbose_name='Curso',
            ),
        ),
    ]
