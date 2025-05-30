# Generated by Django 5.1.5 on 2025-04-12 18:14

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0025_alter_grade_exam'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParsedStudentAnswers',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('student_name', models.CharField(default='Empty', max_length=255)),
                ('student_id', models.CharField(blank=True, max_length=50)),
                ('answers_json', models.JSONField(default=dict)),
                ('extracted_text', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('exam', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parsed_answers', to='exams.exam')),
                ('merged_from', models.ManyToManyField(to='exams.studentpaper')),
            ],
        ),
    ]
