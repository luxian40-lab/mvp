from django.db import migrations, models


def copiar_visible_aula_a_studio(apps, schema_editor):
    Curso = apps.get_model('core', 'Curso')
    Curso.objects.filter(visible_en_aula=True).update(visible_en_studio=True)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0114_estudiante_foto_perfil'),
    ]

    operations = [
        migrations.AddField(
            model_name='curso',
            name='visible_en_studio',
            field=models.BooleanField(
                default=False,
                help_text='Si está activo, el curso aparece en studio.eki.technology para que estudiantes elegibles se inscriban. El estudio se hace en el aula virtual.',
                verbose_name='Publicado en eki Studio',
            ),
        ),
        migrations.RunPython(copiar_visible_aula_a_studio, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='curso',
            name='visible_en_aula',
            field=models.BooleanField(
                default=False,
                help_text='Reservado para listados internos. El catálogo público de inscripción vive en eki Studio (visible_en_studio).',
                verbose_name='Visible en aula (catálogo interno)',
            ),
        ),
    ]
