# Generated by Django 5.1.5 on 2025-04-10 16:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_alter_customuser_profile_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='username',
            field=models.CharField(help_text='Required. 150 characters or fewer.', max_length=150, unique=True),
        ),
    ]
