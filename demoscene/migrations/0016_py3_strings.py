# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-11-19 23:15
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('demoscene', '0015_change_real_name_permission'),
    ]

    operations = [
        migrations.AlterField(
            model_name='accountprofile',
            name='demozoo0_id',
            field=models.IntegerField(blank=True, null=True, verbose_name='Demozoo v0 ID'),
        ),
        migrations.AlterField(
            model_name='blacklistedtag',
            name='message',
            field=models.TextField(blank=True, help_text='Message to show to the user when they try to use the tag (optional)'),
        ),
        migrations.AlterField(
            model_name='blacklistedtag',
            name='replacement',
            field=models.CharField(blank=True, help_text='What to replace the tag with (leave blank to delete it completely)', max_length=255),
        ),
        migrations.AlterField(
            model_name='blacklistedtag',
            name='tag',
            field=models.CharField(help_text='The tag to be blacklisted', max_length=255),
        ),
        migrations.AlterField(
            model_name='captchaquestion',
            name='answer',
            field=models.CharField(help_text='Answers are not case sensitive (the correct answer will be accepted regardless of capitalisation)', max_length=255),
        ),
        migrations.AlterField(
            model_name='captchaquestion',
            name='question',
            field=models.TextField(help_text='HTML is allowed. Keep questions factual and simple - remember that our potential users are not always followers of mainstream demoparty culture'),
        ),
        migrations.AlterField(
            model_name='nick',
            name='abbreviation',
            field=models.CharField(blank=True, help_text="(optional - only if there's one that's actively being used. Don't just make one up!)", max_length=255),
        ),
        migrations.AlterField(
            model_name='nick',
            name='differentiator',
            field=models.CharField(blank=True, help_text='hint text to distinguish from other groups/sceners with the same name - e.g. platform or country', max_length=32),
        ),
        migrations.AlterField(
            model_name='releaser',
            name='demozoo0_id',
            field=models.IntegerField(blank=True, null=True, verbose_name='Demozoo v0 ID'),
        ),
        migrations.AlterField(
            model_name='releaser',
            name='real_name_note',
            field=models.TextField(blank=True, default='', help_text='Details of any correspondence / decision about whether this name should be public', verbose_name='Permission note'),
        ),
        migrations.AlterField(
            model_name='releaserexternallink',
            name='source',
            field=models.CharField(blank=True, editable=False, help_text='Identifier to indicate where this link came from - e.g. manual (entered via form), match, auto', max_length=32),
        ),
        migrations.AlterField(
            model_name='tagdescription',
            name='description',
            field=models.TextField(help_text="HTML is allowed. Keep this to a couple of sentences at most - it's used in tooltips as well as the tag listing page"),
        ),
    ]