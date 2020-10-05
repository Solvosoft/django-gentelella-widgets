from django.core.management import BaseCommand
from django.contrib.staticfiles import finders
import os
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

        libs = {
            'bootstrap': [
                'https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css',
                'https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css.map',
                'https://cdnjs.cloudflare.com/ajax/libs/twitter-bootstrap/3.3.7/js/bootstrap.min.js',

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
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/2.1.24/daterangepicker.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/2.1.24/daterangepicker.min.js.map',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/2.1.24/daterangepicker.min.css',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/2.1.24/daterangepicker.min.css.map',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/2.1.24/moment.min.js'
            ],
            'bootstrap-datetimepicker': [
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-datetimepicker/4.17.47/js/bootstrap-datetimepicker.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-datetimepicker/4.17.47/css/bootstrap-datetimepicker.min.css.map',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-datetimepicker/4.17.47/css/bootstrap-datetimepicker.min.css'
            ],
            'select2': [
                'https://cdnjs.cloudflare.com/ajax/libs/select2/4.0.13/js/select2.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/select2/4.0.13/css/select2.min.css'
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
            ],
            'nprogress': [
                'https://cdnjs.cloudflare.com/ajax/libs/nprogress/0.2.0/nprogress.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/nprogress/0.2.0/nprogress.min.css',
            ],
            'jquery': [
                'https://cdnjs.cloudflare.com/ajax/libs/jquery/2.2.3/jquery.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/jquery/2.2.3/jquery.min.map'
            ],
            'jquery-knob': [
                'https://cdnjs.cloudflare.com/ajax/libs/jQuery-Knob/1.2.13/jquery.knob.min.js',
            ],
            'inputmask': [
                'https://cdnjs.cloudflare.com/ajax/libs/inputmask/3.3.11/inputmask/inputmask.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/inputmask/3.3.11/inputmask/jquery.inputmask.min.js',
            ],
            'moment': [
                'https://cdnjs.cloudflare.com/ajax/libs/moment.js/2.13.0/moment-with-locales.min.js'
            ],
            'bootstrap-wysiwyg': [
                'https://raw.githubusercontent.com/steveathon/bootstrap-wysiwyg/1.0.4/js/bootstrap-wysiwyg.min.js',
            ],
            'parsleyjs': [
                'https://cdnjs.cloudflare.com/ajax/libs/parsley.js/2.3.13/parsley.min.js'
            ],
            'autosize': [
                'https://cdnjs.cloudflare.com/ajax/libs/autosize.js/3.0.15/autosize.min.js'
            ],
            'bootstrap-maxlength': [
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-maxlength/1.9.0/bootstrap-maxlength.min.js'
            ],
            'tail.select': [
                'https://cdn.jsdelivr.net/npm/tail.select@0.5.15/css/bootstrap3/tail.select-default.min.css',
                'https://cdn.jsdelivr.net/npm/tail.select@0.5.15/css/bootstrap3/tail.select-default.min.map',
                'https://cdn.jsdelivr.net/npm/tail.select@0.5.15/js/tail.select-full.min.js',
            ],
            'flag-icon-css': [
                'https://cdnjs.cloudflare.com/ajax/libs/flag-icon-css/3.4.6/css/flag-icon.min.css',
            ],
            'flags/1x1': ['https://cdnjs.cloudflare.com/ajax/libs/flag-icon-css/3.4.6/flags/1x1/%s.svg' % flag for flag in FLAGS],
            'flags/4x3': ['https://cdnjs.cloudflare.com/ajax/libs/flag-icon-css/3.4.6/flags/4x3/%s.svg' % flag for flag in FLAGS],
            'datatables': [
                'https://cdn.datatables.net/1.10.20/js/jquery.dataTables.min.js',
                'https://cdn.datatables.net/1.10.20/js/dataTables.bootstrap.min.js',
                'https://cdn.datatables.net/1.10.20/css/dataTables.bootstrap.min.css',
            ],
            'fileupload': [
                'https://cdnjs.cloudflare.com/ajax/libs/blueimp-file-upload/10.8.0/js/jquery.fileupload.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/blueimp-file-upload/10.8.0/js/jquery.iframe-transport.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/blueimp-file-upload/10.8.0/js/vendor/jquery.ui.widget.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/spark-md5/3.0.0/spark-md5.min.js',
            ],
            'interact': [
                'https://cdn.jsdelivr.net/npm/interactjs/dist/interact.min.js'
            ],

            'chartjs': [
                'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/2.9.3/Chart.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/2.9.3/Chart.min.css'
            ],

            'bootstrap-colorpicker': [
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
            'froala-wysiwyg':[
                'https://cdnjs.cloudflare.com/ajax/libs/froala-editor/3.2.2/css/froala_editor.pkgd.min.css',
                'https://cdnjs.cloudflare.com/ajax/libs/froala-editor/3.2.2/js/froala_editor.pkgd.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/froala-editor/3.2.2/js/third_party/image_tui.min.js'
            ]
        }
        if not os.path.exists(basepath / 'flags'):
            os.mkdir(basepath / 'flags')
        for lib in libs:
            currentbasepath = basepath / lib
            if not os.path.exists(currentbasepath):
                os.mkdir(currentbasepath)
            for staticfile in libs[lib]:
                self.get_static_file(requests, staticfile, currentbasepath)
