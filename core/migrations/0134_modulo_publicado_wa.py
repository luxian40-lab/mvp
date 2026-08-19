# Generated manually — publicación WA módulos

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0133_alter_campana_curso_destino_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='modulo',
            name='publicado_wa',
            field=models.BooleanField(
                default=True,
                help_text=(
                    'Si está activo, el bot puede enviar este módulo al avanzar. '
                    'Los módulos nuevos en admin empiezan en borrador hasta publicar.'
                ),
                verbose_name='Publicado para WhatsApp',
            ),
        ),
    ]
