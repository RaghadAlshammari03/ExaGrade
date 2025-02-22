# Generated by Django 5.1.5 on 2025-02-03 10:06

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('courses', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Exam',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(choices=[('done', 'Done'), ('progress', 'Progress'), ('pending', 'Pending'), ('requires_attention', 'Requires Attention')], default='pending', max_length=20)),
                ('student_papers', models.FileField(upload_to='exams/student_papers/')),
                ('solution_module', models.FileField(blank=True, null=True, upload_to='exams/solution_modules/')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exams', to='courses.course')),
                ('instructor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exams', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
