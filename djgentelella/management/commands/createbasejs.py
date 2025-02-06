from pathlib import Path

from django.contrib.staticfiles import finders
from django.core.management import BaseCommand


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
            'dateranges_gridslider.js',
            'booleanFields.js',
            'editorTinymce.js',
            'wysiwyg.js',
            'gigapixel_storymap.js',
            'mapbased_storymap.js',
            'storyline.js',
            'calendar.js',
            'timeline.js',
            'mediarecord.js'
        ]
        jquery_plugins = [
            'notifications.js',
            'chart.js',
            'custom.widgets.js',
            'fileupload.widget.js',
            'select2related.js',
        ]
        digital_signature = [
            'pdfviewer.js',
            'signature.js',
            'document_manager.js',
        ]

        with open(basepath / 'base.js', 'w') as fwriter:
            # load jquery plugins
            fwriter.write("(function($){\n")
            for f in jquery_plugins:
                with open(basepath / 'base' / f, 'r') as rfile:
                    fwriter.write("\n%s\n" % (rfile.read()))
            fwriter.write("})(jQuery)\n")

            # load base files
            for f in basefiles:
                with open(basepath / 'base' / f, 'r') as rfile:
                    fwriter.write("\n%s\n" % (rfile.read()))

            # load digital signature files
            for f in digital_signature:
                with open(basepath / 'digital_signature' / f, 'r') as rfile:
                    fwriter.write("\n%s\n" % (rfile.read()))
