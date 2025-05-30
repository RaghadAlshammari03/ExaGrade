# Generated by Django 5.1.5 on 2025-04-16 04:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0026_parsedstudentanswers'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentpaper',
            name='group_key',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='studentpaper',
            name='is_merged',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='studentpaper',
            name='needs_regrading',
            field=models.BooleanField(default=False),
        ),
        migrations.DeleteModel(
            name='ParsedStudentAnswers',
        ),
    ]
