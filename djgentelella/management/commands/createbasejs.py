from django.core.management import BaseCommand
from django.contrib.staticfiles import finders
import os
from pathlib import Path


class Command(BaseCommand):
    def handle(self, *args, **options):
        result = finders.find(Path('gentelella/js/widgets.js'))
        if result is None:
            print('No static folder found')
            exit(1)

        basepath = Path(result.replace('widgets.js', ''))

        basefiles = [
            'formset.js',
            'helper_widget.js',
            'autocompleteSelect2.js',
            'select2_wrap.js',
            'dateranges.js',
            'booleanFields.js'
        ]
        jquery_plugins = [
            'notifications.js',
            'chart.js',
            'custom.widgets.js',
            'fileupload.widget.js',
            'select2related.js',
        ]

        with open(basepath / 'base.js', 'w') as fwriter:
            fwriter.write("(function($){\n")
            for f in jquery_plugins:
                with open(basepath / 'base' / f, 'r') as rfile:
                    fwriter.write("\n%s\n"%(rfile.read()))
            fwriter.write("})(jQuery)\n")

            for f in basefiles:
                with open(basepath / 'base' / f, 'r') as rfile:
                    fwriter.write("\n%s\n"%(rfile.read()))
