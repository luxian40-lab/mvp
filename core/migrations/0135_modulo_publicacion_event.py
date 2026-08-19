# Generated manually — historial diff publicación WA

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0134_modulo_publicado_wa'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModuloPublicacionEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accion', models.CharField(
                    choices=[('publicar', 'Publicar'), ('qa_validar', 'QA pre-publicar')],
                    default='publicar',
                    max_length=20,
                )),
                ('snapshot_antes', models.JSONField(blank=True, default=dict)),
                ('snapshot_despues', models.JSONField(blank=True, default=dict)),
                ('diff_resumen', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('modulo', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='eventos_publicacion',
                    to='core.modulo',
                )),
                ('usuario', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Evento publicación módulo',
                'verbose_name_plural': 'Eventos publicación módulo',
                'ordering': ('-created_at',),
            },
        ),
    ]
