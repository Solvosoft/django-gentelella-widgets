from django.core.management import BaseCommand
from django.contrib.staticfiles import finders
import os
import shutil
from pathlib import Path

FLAGS = ['ad', 'ae', 'af', 'ag', 'ai', 'al', 'am', 'ao', 'aq', 'ar', 'as', 'at', 'au', 'aw', 'ax', 'az', 'ba', 'bb', 'bd', 'be', 'bf', 'bg', 'bh', 'bi', 'bj', 'bl', 'bm', 'bn', 'bo', 'bq', 'br', 'bs', 'bt', 'bv', 'bw', 'by', 'bz', 'ca', 'cc', 'cd', 'cf', 'cg', 'ch', 'ci', 'ck', 'cl', 'cm', 'cn', 'co', 'cr', 'cu', 'cv', 'cw', 'cx', 'cy', 'cz', 'de', 'dj', 'dk', 'dm', 'do', 'dz', 'ec', 'ee', 'eg', 'eh', 'er', 'es-ca', 'es', 'et', 'eu', 'fi', 'fj', 'fk', 'fm', 'fo', 'fr', 'ga', 'gb-eng', 'gb-nir', 'gb-sct', 'gb-wls', 'gb', 'gd', 'ge', 'gf', 'gg', 'gh', 'gi', 'gl', 'gm', 'gn', 'gp', 'gq', 'gr', 'gs', 'gt', 'gu', 'gw', 'gy', 'hk', 'hm', 'hn', 'hr', 'ht', 'hu', 'id', 'ie', 'il', 'im', 'in', 'io', 'iq', 'ir', 'is', 'it', 'je', 'jm', 'jo', 'jp', 'ke', 'kg', 'kh', 'ki', 'km', 'kn',
         'kp', 'kr', 'kw', 'ky', 'kz', 'la', 'lb', 'lc', 'li', 'lk', 'lr', 'ls', 'lt', 'lu', 'lv', 'ly', 'ma', 'mc', 'md', 'me', 'mf', 'mg', 'mh', 'mk', 'ml', 'mm', 'mn', 'mo', 'mp', 'mq', 'mr', 'ms', 'mt', 'mu', 'mv', 'mw', 'mx', 'my', 'mz', 'na', 'nc', 'ne', 'nf', 'ng', 'ni', 'nl', 'no', 'np', 'nr', 'nu', 'nz', 'om', 'pa', 'pe', 'pf', 'pg', 'ph', 'pk', 'pl', 'pm', 'pn', 'pr', 'ps', 'pt', 'pw', 'py', 'qa', 're', 'ro', 'rs', 'ru', 'rw', 'sa', 'sb', 'sc', 'sd', 'se', 'sg', 'sh', 'si', 'sj', 'sk', 'sl', 'sm', 'sn', 'so', 'sr', 'ss', 'st', 'sv', 'sx', 'sy', 'sz', 'tc', 'td', 'tf', 'tg', 'th', 'tj', 'tk', 'tl', 'tm', 'tn', 'to', 'tr', 'tt', 'tv', 'tw', 'tz', 'ua', 'ug', 'um', 'un', 'us', 'uy', 'uz', 'va', 'vc', 've', 'vg', 'vi', 'vn', 'vu', 'wf', 'ws', 'xk', 'ye', 'yt', 'za', 'zm', 'zw']


class Command(BaseCommand):
    help = "Load static files for development command"

    def get_static_file(self, requests, url, basepath):
        name = url.split('/')[-1]
        if not os.path.exists(basepath / name):
            print("Downloading %s --> %s" % (url, basepath / name))
            r = requests.get(url)
            with open(basepath / name, 'wb') as arch:
                arch.write(r.content)

    def get_static_list_file(self, requests, files, basepath):
        if not os.path.exists(basepath):
            print("Downloading %s " % (basepath,))
            with open(basepath, 'wb') as arch:
                for url in files:
                    r = requests.get(url)
                    arch.write(r.content)
                    arch.write(b'\n')

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Delete delete before start',
        )

    def handle(self, *args, **options):
        try:
            import requests
        except:
            print("Requests is required try pip install requests")
            exit(1)

        result = finders.find(Path('gentelella/css/custom.css'))
        if result is None:
            print('No static folder found')
            exit(1)

        basepath = Path(result.replace(
            str(Path('gentelella/css/custom.css')), 'vendors/'))

        if options['delete']:
            shutil.rmtree(basepath)
            basepath.mkdir()

        libs = {
            'bootstrap': [
                'https://cdn.jsdelivr.net/npm/bootstrap@5.2.0/dist/css/bootstrap.min.css',
                'https://cdn.jsdelivr.net/npm/bootstrap@5.2.0/dist/js/bootstrap.min.js',
                'https://cdn.jsdelivr.net/npm/@popperjs/core@2.11.5/dist/umd/popper.min.js',
                'https://cdn.jsdelivr.net/npm/bootstrap@5.2.0/dist/js/bootstrap.bundle.min.js'
            ],
            'fonts': [
                'https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/fonts/glyphicons-halflings-regular.eot',
                'https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/fonts/glyphicons-halflings-regular.ttf',
                'https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/fonts/glyphicons-halflings-regular.woff2',
                'https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/fonts/glyphicons-halflings-regular.svg',
                'https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/fonts/glyphicons-halflings-regular.woff',
                'https://cdnjs.cloudflare.com/ajax/libs/twitter-bootstrap/3.3.7/fonts/glyphicons-halflings-regular.svg',
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/fonts/fontawesome-webfont.svg',
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/fonts/FontAwesome.otf',
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/fonts/fontawesome-webfont.eot',
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/fonts/fontawesome-webfont.ttf',
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/fonts/fontawesome-webfont.woff',
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/fonts/fontawesome-webfont.woff2',
            ],
            'font-awesome': [

                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css',
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.css.map'
            ],
            'bootstrap-daterangepicker': [
                #'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/3.1/daterangepicker.min.js',
                #'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/3.1/daterangepicker.min.css',
                #'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/3.1/moment.min.js',
                '',
                '',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/3.0.5/daterangepicker.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/3.0.5/daterangepicker.min.css',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/3.0.5/daterangepicker.min.css.map',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/3.0.5/daterangepicker.min.js.map',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/3.0.5/moment.min.js'
            ],
            'bootstrap-datetimepicker': [
                #'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-datetimepicker/6.0.1/css/tempus-dominus.min.css',
                #'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-datetimepicker/6.0.1/js/tempus-dominus.min.js',

                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-datetimepicker/4.17.47/js/bootstrap-datetimepicker.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-datetimepicker/4.17.47/css/bootstrap-datetimepicker.min.css.map',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-datetimepicker/4.17.47/css/bootstrap-datetimepicker.min.css'
            ],
            'select2': [
                'https://cdnjs.cloudflare.com/ajax/libs/select2/4.1.0-rc.0/js/select2.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/select2/4.1.0-rc.0/css/select2.min.css',
                'https://cdn.jsdelivr.net/npm/select2-bootstrap-5-theme@1.3.0/dist/select2-bootstrap-5-theme.min.css'
                #'https://cdnjs.cloudflare.com/ajax/libs/select2/4.0.13/js/select2.min.js',
                #'https://cdnjs.cloudflare.com/ajax/libs/select2/4.0.13/css/select2.min.css'
            ],
            'switchery': [
                'https://cdnjs.cloudflare.com/ajax/libs/switchery/0.8.2/switchery.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/switchery/0.8.2/switchery.min.css',
            ],
            'iCheck': [
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.2/icheck.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.2/skins/flat/green.css',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.2/skins/flat/blue.css',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.2/skins/flat/aero.css',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.2/skins/flat/yellow.css',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.2/skins/flat/orange.css',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.2/skins/flat/green.png',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.2/skins/flat/blue.png',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.2/skins/flat/aero.png',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.2/skins/flat/yellow.png',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.2/skins/flat/orange.png',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.2/skins/flat/green@2x.png',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.2/skins/flat/blue@2x.png',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.2/skins/flat/aero@2x.png',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.2/skins/flat/yellow@2x.png',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.2/skins/flat/orange@2x.png',
            ],
            'bootstrap-progressbar': [

                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-progressbar/0.9.0/bootstrap-progressbar.min.js',
                'https://cdn.jsdelivr.net/npm/bootstrap-progressbar@0.9.0/css/bootstrap-progressbar-3.3.4.min.css',
                ##'https://cdn.jsdelivr.net/npm/bootstrap-progressbar@0.9.0/css/bootstrap-progressbar-3.3.4.min.css',
            ],
            'nprogress': [
                'https://cdnjs.cloudflare.com/ajax/libs/nprogress/0.2.0/nprogress.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/nprogress/0.2.0/nprogress.min.css',
                ##'https://cdnjs.cloudflare.com/ajax/libs/nprogress/0.2.0/nprogress.min.js',
                ##'https://cdnjs.cloudflare.com/ajax/libs/nprogress/0.2.0/nprogress.min.css',
            ],
            'jquery': [
                'https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.1/jquery.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.1/jquery.min.map',
                #'https://cdnjs.cloudflare.com/ajax/libs/jquery/2.2.3/jquery.min.js',
                #'https://cdnjs.cloudflare.com/ajax/libs/jquery/2.2.3/jquery.min.map'
            ],
            'jquery-ui': [
                'https://cdnjs.cloudflare.com/ajax/libs/jqueryui/1.13.2/themes/smoothness/jquery-ui.min.css',
                #'https://code.jquery.com/ui/1.11.3/themes/smoothness/jquery-ui.css'
            ],
            'jquery-knob': [
                'https://cdnjs.cloudflare.com/ajax/libs/jQuery-Knob/1.2.13/jquery.knob.min.js',
            ],
            'inputmask': [
                #'https://cdnjs.cloudflare.com/ajax/libs/jquery.inputmask/5.0.7/inputmask.min.js',
                #'https://cdnjs.cloudflare.com/ajax/libs/jquery.inputmask/5.0.7/jquery.inputmask.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/inputmask/3.3.11/inputmask/inputmask.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/inputmask/3.3.11/inputmask/jquery.inputmask.min.js',
            ],
            'moment': [
                'https://cdnjs.cloudflare.com/ajax/libs/moment.js/2.13.0/moment-with-locales.min.js'
            ],
            'parsleyjs': [
                'https://cdnjs.cloudflare.com/ajax/libs/parsley.js/2.3.13/parsley.min.js'
            ],
            'autosize': [
                'https://cdnjs.cloudflare.com/ajax/libs/autosize.js/3.0.15/autosize.min.js'
            ],
            'bootstrap-maxlength': [
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-maxlength/1.10.0/bootstrap-maxlength.min.js',
                #'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-maxlength/1.9.0/bootstrap-maxlength.min.js'
            ],
            'flag-icon-css': [
                'https://cdnjs.cloudflare.com/ajax/libs/flag-icon-css/6.6.6/css/flag-icons.min.css',
                #'https://cdnjs.cloudflare.com/ajax/libs/flag-icon-css/3.4.6/css/flag-icon.min.css',
            ],
            'flags/1x1': ['https://cdnjs.cloudflare.com/ajax/libs/flag-icon-css/3.4.6/flags/1x1/%s.svg' % flag for flag in FLAGS],
            'flags/4x3': ['https://cdnjs.cloudflare.com/ajax/libs/flag-icon-css/3.4.6/flags/4x3/%s.svg' % flag for flag in FLAGS],
            'datatables': [
                'https://cdn.datatables.net/v/bs5/jszip-2.5.0/dt-1.12.1/af-2.4.0/b-2.2.3/b-colvis-2.2.3/b-html5-2.2.3/b-print-2.2.3/cr-1.5.6/date-1.1.2/fc-4.1.0/fh-3.2.4/kt-2.7.0/r-2.3.0/rg-1.2.0/rr-1.2.8/sc-2.0.7/sb-1.3.4/sp-2.0.2/sl-1.4.0/sr-1.1.1/datatables.min.js',
                'https://cdn.datatables.net/v/bs5/jszip-2.5.0/dt-1.12.1/af-2.4.0/b-2.2.3/b-colvis-2.2.3/b-html5-2.2.3/b-print-2.2.3/cr-1.5.6/date-1.1.2/fc-4.1.0/fh-3.2.4/kt-2.7.0/r-2.3.0/rg-1.2.0/rr-1.2.8/sc-2.0.7/sb-1.3.4/sp-2.0.2/sl-1.4.0/sr-1.1.1/datatables.min.css'

            ],
            'fileupload': [
                'https://cdnjs.cloudflare.com/ajax/libs/blueimp-file-upload/10.32.0/js/jquery.fileupload.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/blueimp-file-upload/10.32.0/js/jquery.iframe-transport.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/blueimp-file-upload/10.32.0/js/vendor/jquery.ui.widget.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/spark-md5/3.0.0/spark-md5.min.js',
            ],
            'fullcalendar': [
                'https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.js',
                'https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/locales-all.js',
                'https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.css',
            ],
            'interact': [
                #'https://cdnjs.cloudflare.com/ajax/libs/interact.js/1.0.2/interact.min.js'
                'https://cdn.jsdelivr.net/npm/interactjs/dist/interact.min.js'
            ],
            'timeline/': [],
            'timeline/css': ["https://cdn.knightlab.com/libs/timeline3/latest/css/timeline.css"],
            'timeline/css/icons/': [
                "https://cdn.knightlab.com/libs/timeline3/latest/css/icons/tl-icons.eot",
                "https://cdn.knightlab.com/libs/timeline3/latest/css/icons/tl-icons.ttf",
                "https://cdn.knightlab.com/libs/timeline3/latest/css/icons/tl-icons.svg",
            ],
            'timeline/js': ["https://cdn.knightlab.com/libs/timeline3/latest/js/timeline.js"],
            'storymapjs': [
                "https://cdn.knightlab.com/libs/storymapjs/latest/js/storymap.js",
                "https://cdn.knightlab.com/libs/storymapjs/latest/css/storymap.css",
            ],
            'css/icons/':[
                'https://cdn.knightlab.com/libs/storymapjs/latest/css/icons/vco-icons.ttf'
            ],
            'chartjs': [
                'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/2.9.3/Chart.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/2.9.3/Chart.min.css'
            ],

            'bootstrap-colorpicker': [
                #'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-colorpicker/3.4.0/js/bootstrap-colorpicker.min.js',
                #'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-colorpicker/3.4.0/css/bootstrap-colorpicker.css'
                'https://colorlib.com/polygon/vendors/mjolnic-bootstrap-colorpicker/dist/css/bootstrap-colorpicker.min.css',
                'https://colorlib.com/polygon/vendors/mjolnic-bootstrap-colorpicker/dist/js/bootstrap-colorpicker.min.js'
            ],
            "img/": [],
            "img/bootstrap-colorpicker": [
                'https://colorlib.com/polygon/vendors/mjolnic-bootstrap-colorpicker/dist/img/bootstrap-colorpicker/alpha.png',
                'https://colorlib.com/polygon/vendors/mjolnic-bootstrap-colorpicker/dist/img/bootstrap-colorpicker/hue.png',
                'https://colorlib.com/polygon/vendors/mjolnic-bootstrap-colorpicker/dist/img/bootstrap-colorpicker/saturation.png',

                'https://colorlib.com/polygon/vendors/mjolnic-bootstrap-colorpicker/dist/img/bootstrap-colorpicker/alpha-horizontal.png',
                'https://colorlib.com/polygon/vendors/mjolnic-bootstrap-colorpicker/dist/img/bootstrap-colorpicker/hue-horizontal.png',
                'https://colorlib.com/polygon/vendors/mjolnic-bootstrap-colorpicker/dist/img/bootstrap-colorpicker/saturation-horizontal.png',
            ],
            'bootstrap-tree': [
                'https://github.com/patternfly/patternfly-bootstrap-treeview/raw/master/dist/bootstrap-treeview.min.js',
                'https://raw.githubusercontent.com/patternfly/patternfly-bootstrap-treeview/master/dist/bootstrap-treeview.min.css'
            ],
            'tagify': [
                'https://cdnjs.cloudflare.com/ajax/libs/tagify/3.18.1/tagify.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/tagify/3.18.1/jQuery.tagify.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/tagify/3.18.1/tagify.min.css'
            ],
            'grid-slider': [
                'https://cdnjs.cloudflare.com/ajax/libs/ion-rangeslider/2.3.1/js/ion.rangeSlider.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/ion-rangeslider/2.3.1/css/ion.rangeSlider.min.css'
            ],
            'sweetalert2': [
                'https://cdn.jsdelivr.net/npm/sweetalert2@10.10.0/dist/sweetalert2.all.min.js',
                'https://cdn.jsdelivr.net/npm/sweetalert2@10.10.0/dist/sweetalert2.min.css'
            ],
            'summernote': [
                'https://cdn.jsdelivr.net/npm/summernote@0.8.18/dist/summernote-lite.min.js',
                'https://cdn.jsdelivr.net/npm/summernote@0.8.18/dist/summernote-lite.min.css'
            ],
            'tinymce': [
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/tinymce.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/jquery.tinymce.min.js',
            ],
            'tinymce/themes/silver': [
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/themes/silver/theme.min.js'
            ],
            'tinymce/themes/mobile/': [
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/themes/mobile/theme.min.js'
            ],
            'tinymce/skins/content/dark/': [
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/skins/content/dark/content.min.css',
            ],
            'tinymce/skins/content/default/': [
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/skins/content/default/content.min.css',
            ],
            'tinymce/skins/content/document': [
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/skins/content/document/content.min.css',
            ],
            'tinymce/skins/content/writer': [
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/skins/content/writer/content.min.css',
            ],
            'tinymce/skins/ui/oxide-dark/': [
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/skins/ui/oxide-dark/content.inline.min.css',
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/skins/ui/oxide-dark/content.min.css',
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/skins/ui/oxide-dark/content.mobile.min.css',
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/skins/ui/oxide-dark/skin.min.css',
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/skins/ui/oxide-dark/skin.mobile.min.css',
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/skins/ui/oxide-dark/skin.shadowdom.min.css',
            ],
            'tinymce/skins/ui/oxide/': [
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/skins/ui/oxide/content.inline.min.css',
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/skins/ui/oxide/content.min.css',
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/skins/ui/oxide/content.mobile.min.css',
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/skins/ui/oxide/skin.min.css',
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/skins/ui/oxide/skin.mobile.min.css',
                'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/skins/ui/oxide/skin.shadowdom.min.css',
            ],
            'storylinejs': [
                'https://cdn.knightlab.com/libs/storyline/1.1.0/css/storyline.css',
                'https://cdn.knightlab.com/libs/storyline/1.1.0/js/storyline.js',
            ]
        }
        compressed = {
            'tinymce': {
                'tinymce-all.js': [
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/icons/default/icons.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/advlist/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/anchor/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/autolink/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/autoresize/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/autosave/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/bbcode/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/charmap/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/code/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/codesample/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/colorpicker/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/contextmenu/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/directionality/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/emoticons/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/fullpage/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/fullscreen/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/help/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/hr/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/image/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/imagetools/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/importcss/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/insertdatetime/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/legacyoutput/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/link/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/lists/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/media/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/nonbreaking/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/noneditable/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/pagebreak/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/paste/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/preview/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/print/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/quickbars/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/save/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/searchreplace/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/spellchecker/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/tabfocus/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/table/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/template/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/textcolor/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/textpattern/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/toc/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/visualblocks/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/visualchars/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/wordcount/plugin.min.js',
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/plugins/emoticons/js/emojis.min.js',
                ],
                'skin.min.css': [
                    'https://cdnjs.cloudflare.com/ajax/libs/tinymce/5.6.1/skins/ui/oxide/skin.min.css',
                ]
            }
        }

        if not os.path.exists(basepath / 'flags'):
            (basepath / 'flags').mkdir(parents=True)
        for lib in libs:
            currentbasepath = basepath / lib
            if not os.path.exists(currentbasepath):
                os.makedirs(currentbasepath)
            for staticfile in libs[lib]:
                self.get_static_file(requests, staticfile, currentbasepath)

        for files in compressed:
            for name in compressed[files]:
                currentbasepath = basepath / files
                currentbasepath = currentbasepath / name
                self.get_static_list_file(requests, compressed[files][name],  currentbasepath)
