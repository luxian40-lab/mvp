from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0207_plantilla_texto_superior_eki'),
    ]

    operations = [
        migrations.CreateModel(
            name='CursoVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.PositiveIntegerField()),
                ('estado', models.CharField(
                    choices=[('borrador', 'Borrador'), ('publicado', 'Publicado'), ('archivado', 'Archivado')],
                    default='borrador',
                    max_length=16,
                )),
                ('ensamblado', models.JSONField(blank=True, default=dict)),
                ('nota', models.CharField(blank=True, default='', max_length=200)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('publicado_en', models.DateTimeField(blank=True, null=True)),
                ('curso', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='versiones',
                    to='core.curso',
                )),
            ],
            options={
                'verbose_name': 'Versión de curso',
                'verbose_name_plural': 'Versiones de curso',
            },
        ),
        migrations.AddField(
            model_name='curso',
            name='version_publicada',
            field=models.ForeignKey(
                blank=True,
                help_text='Con EKI_CURSO_VERSIONES apagado no se usa. Publicar no mueve a quien ya estudia.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='core.cursoversion',
                verbose_name='Versión publicada',
            ),
        ),
        migrations.AddField(
            model_name='progresoestudiante',
            name='curso_version',
            field=models.ForeignKey(
                blank=True,
                help_text='Con EKI_CURSO_VERSIONES apagado queda vacío; la entrega sigue el curso vivo.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='progresos',
                to='core.cursoversion',
                verbose_name='Versión del curso',
            ),
        ),
        migrations.AddConstraint(
            model_name='cursoversion',
            constraint=models.UniqueConstraint(
                fields=('curso', 'numero'),
                name='uniq_curso_version_numero',
            ),
        ),
        migrations.AddIndex(
            model_name='cursoversion',
            index=models.Index(fields=['curso', 'estado'], name='curso_version_estado'),
        ),
    ]
