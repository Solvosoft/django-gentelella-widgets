import hashlib
import os
import re
import shutil
from pathlib import Path
from threading import Thread, current_thread

from django.contrib.staticfiles import finders
from django.core.management import BaseCommand

try:
    import requests
except BaseException:
    print("Requests is required try pip install requests")
    exit(1)


def _is_html_error_page(content):
    # Some CDNs (friconix.com's included) answer a dead path with 200 and
    # their normal HTML homepage instead of a 404 -- status alone won't
    # catch that, and writing it as the "library" corrupts every bundle
    # it gets concatenated into.
    head = content[:512].lstrip().lower()
    return head.startswith(b'<!doctype html') or head.startswith(b'<html')


def _mdi_woff2_only(content):
    """Point Material Design Icons' @font-face at the woff2 alone.

    Its stylesheet lists eot, woff2, woff and ttf -- 2.3 MB of the same glyphs
    in four encodings, of which every browser this project supports picks the
    403 KB woff2. Only that one is downloaded, so the other three URLs would be
    dead: harmless for the rendering, a 404 in the network tab for whoever goes
    looking.
    """
    woff2 = re.search(rb'url\("([^"]*\.woff2[^"]*)"\)', content)
    if not woff2:  # upstream changed shape -- leave it alone rather than guess
        return content
    return re.sub(rb'src:url\([^)]*\.eot[^)]*\);src:[^;]*;',
                  b'src:url("%s") format("woff2");' % woff2.group(1),
                  content, count=1)


# Sources that serve no version, so a pin is impossible and the only defence
# against the code changing under us is to record what was last vetted.
#
# Knightlab publishes numbered releases, but they are not the same software:
# `latest` is the current webpack build (storymap.js, 260 KB, KLStoryMap
# namespace) while the newest tag, 0.7.1, is unminified 2019 code on the old VCO
# architecture, twice the size. Pinning to it would be a four-year downgrade,
# not a pin. friconix has no version at all -- its npm package was unpublished
# in 2020 and there is no repository.
#
# A mismatch is reported, not fatal: upstream is allowed to move, but nobody
# should find out by accident. Verify the new build, then paste the new hash.
PINNED_CHECKSUMS = {
    'https://cdn.knightlab.com/libs/storymapjs/latest/js/storymap.js':
        'c9ce90e87a0b78dfad5d5cba29848302cc3804a68fc9c6bc41d4e37bcf0a8c03',
    'https://cdn.knightlab.com/libs/storymapjs/latest/css/storymap.css':
        '6bda7de7c58eecf3e247bebdbc2deacc5974c51f76bf2012c4fa4123fc6e2076',
    'https://cdn.knightlab.com/libs/timeline3/latest/js/timeline.js':
        '8d87fa72477f5ed45f1ec5e4df08a2379d6c7524790f0523d555c3af72842863',
    'https://cdn.knightlab.com/libs/timeline3/latest/css/timeline.css':
        'bf78018d195b3b47e934585b78da0c0b620868c3f29b923164dcf302235484f4',
    'https://friconix.com/cdn/friconix.js':
        'd1d8bea7160815e06bd384008dba74155c61299be7533bda60940636250564ab',
}

# Filled by the download threads, reported once at the end of the command --
# a warning printed among two hundred download lines is a warning nobody reads.
CHECKSUM_MISMATCHES = []


# Rewrites applied to a downloaded file, keyed by its name.
POST_PROCESS = {
    'materialdesignicons.min.css': _mdi_woff2_only,
}


def download(urls):
    thread = current_thread()
    for url in urls:
        download_url = url[0]
        filename = url[1]
        print("%s) Downloading %s --> %s" % (thread.name, download_url, filename))
        r = requests.get(download_url)
        if not r.ok or _is_html_error_page(r.content):
            # Don't save the error page as the file, don't raise either --
            # a few CDN paths are permanently gone, that shouldn't kill the thread.
            print("%s) FAILED (%s): %s" % (thread.name, r.status_code, download_url))
            continue
        content = r.content
        expected = PINNED_CHECKSUMS.get(download_url)
        if expected is not None:
            actual = hashlib.sha256(content).hexdigest()
            if actual != expected:
                CHECKSUM_MISMATCHES.append((download_url, expected, actual))
        post_process = POST_PROCESS.get(Path(filename).name)
        if post_process is not None:
            content = post_process(content)
        with open(filename, 'wb') as arch:
            arch.write(content)


class Command(BaseCommand):
    help = "Load static files for development command"
    urls = []
    threads_count = 10

    def get_urls_list(self, urls):
        """Split urls into at most threads_count chunks, losing none of them.

        The previous version walked `while nextt != end`, which dropped the
        final chunk whenever len(urls) was an exact multiple of trunk_len --
        silently, so a library simply never appeared under vendors/.
        """
        if self.threads_count <= 1 or self.threads_count >= len(urls):
            yield urls[:]
            return
        trunk_len = -(-len(urls) // self.threads_count)  # ceil
        for start in range(0, len(urls), trunk_len):
            yield urls[start:start + trunk_len]

    def download_urls(self):
        threads = []
        for urls_trunk in self.get_urls_list(self.urls):
            if urls_trunk:
                t = Thread(target=download, args=[urls_trunk])
                t.start()
                threads.append(t)

        for t in threads:
            t.join()

    def get_static_file(self, url, basepath):
        name = url.split('/')[-1]
        if not os.path.exists(basepath / name):
            self.urls.append(
                (url, basepath / name)
            )

    def get_static_list_file(self, files, basepath):
        if not os.path.exists(basepath):
            print("Downloading %s " % (basepath,))
            with open(basepath, 'wb') as arch:
                for url in files:
                    r = requests.get(url)
                    if not r.ok or _is_html_error_page(r.content):
                        print("FAILED (%s): %s" % (r.status_code, url))
                        continue
                    arch.write(r.content)
                    arch.write(b'\n')

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Delete delete before start',
        )
        parser.add_argument('--threads', type=int, default=10,
                            help='Number of downloading threads')

    def handle(self, *args, **options):
        self.threads_count = options['threads']
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
                'https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css',
                'https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.min.js',
                'https://cdn.jsdelivr.net/npm/@popperjs/core@2.11.8/dist/umd/popper.min.js',
                'https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js'
            ],
            'fonts': [
                # Only Font Awesome's own faces belong here: font-awesome.min.css
                # reaches them as ../fonts/ and urlreplace inlines them at bundle
                # time. Bootstrap 3's glyphicons used to be downloaded alongside
                # them and no bundled stylesheet has ever referenced one.
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/fonts/fontawesome-webfont.svg',
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/fonts/FontAwesome.otf',
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/fonts/fontawesome-webfont.eot',
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/fonts/fontawesome-webfont.ttf',
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/fonts/fontawesome-webfont.woff',
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/fonts/fontawesome-webfont.woff2',
            ],
            # Material Design Icons: 7448 icons as a webfont, opt-in through
            # the `use_mdi` define. Not in any pylp bundle on purpose -- urlreplace
            # would base64 the font into the vendors stylesheet, and the whole
            # point of a webfont is that the browser fetches one 403 KB woff2 and
            # caches it. Keeping upstream's css/ + fonts/ layout is what makes the
            # stylesheet's own ../fonts/ reference resolve.
            'mdi/css': [
                'https://cdn.jsdelivr.net/npm/@mdi/font@7.4.47/css/'
                'materialdesignicons.min.css',
            ],
            'mdi/fonts': [
                'https://cdn.jsdelivr.net/npm/@mdi/font@7.4.47/fonts/'
                'materialdesignicons-webfont.woff2',
            ],
            'font-awesome': [
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css',
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.css.map'
            ],
            'friconix': [
                "https://friconix.com/cdn/friconix.js"
            ],
            'bootstrap-daterangepicker': [
                # 'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/3.1/daterangepicker.min.js',
                # 'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/3.1/daterangepicker.min.css',
                # 'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/3.1/moment.min.js',
                '',
                '',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/3.0.5/daterangepicker.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/3.0.5/daterangepicker.min.css',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/3.0.5/daterangepicker.min.css.map',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/3.0.5/daterangepicker.min.js.map',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-daterangepicker/3.0.5/moment.min.js'
            ],
            'bootstrap-datetimepicker': [
                # 'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-datetimepicker/6.0.1/css/tempus-dominus.min.css',
                # 'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-datetimepicker/6.0.1/js/tempus-dominus.min.js',

                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-datetimepicker/4.17.47/js/bootstrap-datetimepicker.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-datetimepicker/4.17.47/css/bootstrap-datetimepicker.min.css'
            ],
            'select2': [
                'https://cdnjs.cloudflare.com/ajax/libs/select2/4.1.0/js/select2.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/select2/4.1.0/css/select2.min.css',
                'https://cdn.jsdelivr.net/npm/select2-bootstrap-5-theme@1.3.0/dist/select2-bootstrap-5-theme.min.css'
                # 'https://cdnjs.cloudflare.com/ajax/libs/select2/4.0.13/js/select2.min.js',
                # 'https://cdnjs.cloudflare.com/ajax/libs/select2/4.0.13/css/select2.min.css'
            ],
            "squirrelly": [
                "https://unpkg.com/squirrelly@9.1.1/dist/browser/squirrelly.min.js"
            ],
            'switchery': [
                'https://cdnjs.cloudflare.com/ajax/libs/switchery/0.8.2/switchery.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/switchery/0.8.2/switchery.min.css',
            ],
            'iCheck': [
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.3/icheck.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.3/skins/flat/green.css',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.3/skins/flat/blue.css',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.3/skins/flat/aero.css',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.3/skins/flat/yellow.css',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.3/skins/flat/orange.css',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.3/skins/flat/green.png',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.3/skins/flat/blue.png',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.3/skins/flat/aero.png',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.3/skins/flat/yellow.png',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.3/skins/flat/orange.png',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.3/skins/flat/green@2x.png',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.3/skins/flat/blue@2x.png',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.3/skins/flat/aero@2x.png',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.3/skins/flat/yellow@2x.png',
                'https://cdnjs.cloudflare.com/ajax/libs/iCheck/1.0.3/skins/flat/orange@2x.png',
            ],
            'bootstrap-progressbar': [

                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-progressbar/0.9.0/bootstrap-progressbar.min.js',
                'https://cdn.jsdelivr.net/npm/bootstrap-progressbar@0.9.0/css/bootstrap-progressbar-3.3.4.min.css',
                # 'https://cdn.jsdelivr.net/npm/bootstrap-progressbar@0.9.0/css/bootstrap-progressbar-3.3.4.min.css',
            ],
            'nprogress': [
                'https://cdnjs.cloudflare.com/ajax/libs/nprogress/0.2.0/nprogress.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/nprogress/0.2.0/nprogress.min.css',
                # 'https://cdnjs.cloudflare.com/ajax/libs/nprogress/0.2.0/nprogress.min.js',
                # 'https://cdnjs.cloudflare.com/ajax/libs/nprogress/0.2.0/nprogress.min.css',
            ],
            'jquery': [
                'https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.1/jquery.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.1/jquery.min.map',
                # 'https://cdnjs.cloudflare.com/ajax/libs/jquery/2.2.3/jquery.min.js',
                # 'https://cdnjs.cloudflare.com/ajax/libs/jquery/2.2.3/jquery.min.map'
            ],
            'jquery-ui': [
                'https://cdnjs.cloudflare.com/ajax/libs/jqueryui/1.13.2/themes/smoothness/jquery-ui.min.css',
                # 'https://code.jquery.com/ui/1.11.3/themes/smoothness/jquery-ui.css'
            ],
            'jquery-knob': [
                'https://cdnjs.cloudflare.com/ajax/libs/jQuery-Knob/1.2.13/jquery.knob.min.js',
            ],
            'inputmask': [
                # 'https://cdnjs.cloudflare.com/ajax/libs/jquery.inputmask/5.0.7/inputmask.min.js',
                # 'https://cdnjs.cloudflare.com/ajax/libs/jquery.inputmask/5.0.7/jquery.inputmask.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/inputmask/3.3.11/inputmask/inputmask.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/inputmask/3.3.11/inputmask/jquery.inputmask.min.js',
            ],
            'moment': [
                'https://cdnjs.cloudflare.com/ajax/libs/moment.js/2.30.1/moment-with-locales.min.js'
            ],
            'parsleyjs': [
                'https://cdnjs.cloudflare.com/ajax/libs/parsley.js/2.9.2/parsley.min.js'
            ],
            'autosize': [
                'https://cdnjs.cloudflare.com/ajax/libs/autosize.js/6.0.1/autosize.min.js'
            ],
            'bootstrap-maxlength': [
                'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-maxlength/1.10.0/bootstrap-maxlength.min.js',
                # 'https://cdnjs.cloudflare.com/ajax/libs/bootstrap-maxlength/1.9.0/bootstrap-maxlength.min.js'
            ],
            'datatables': [
                'https://cdn.datatables.net/v/bs5/jszip-2.5.0/dt-1.12.1/af-2.4.0/b-2.2.3/b-colvis-2.2.3/b-html5-2.2.3/b-print-2.2.3/cr-1.5.6/date-1.1.2/fc-4.1.0/fh-3.2.4/kt-2.7.0/r-2.3.0/rg-1.2.0/rr-1.2.8/sc-2.0.7/sb-1.3.4/sp-2.0.2/sl-1.4.0/sr-1.1.1/datatables.min.js',
                'https://cdn.datatables.net/v/bs5/jszip-2.5.0/dt-1.12.1/af-2.4.0/b-2.2.3/b-colvis-2.2.3/b-html5-2.2.3/b-print-2.2.3/cr-1.5.6/date-1.1.2/fc-4.1.0/fh-3.2.4/kt-2.7.0/r-2.3.0/rg-1.2.0/rr-1.2.8/sc-2.0.7/sb-1.3.4/sp-2.0.2/sl-1.4.0/sr-1.1.1/datatables.min.css',
                "https://cdn.datatables.net/plug-ins/1.12.1/i18n/en-GB.json",
                "http://cdn.datatables.net/plug-ins/1.12.1/i18n/es-ES.json"

            ],
            'fileupload': [
                'https://cdnjs.cloudflare.com/ajax/libs/blueimp-file-upload/10.32.0/js/jquery.fileupload.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/blueimp-file-upload/10.32.0/js/jquery.iframe-transport.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/blueimp-file-upload/10.32.0/js/vendor/jquery.ui.widget.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/spark-md5/3.0.2/spark-md5.min.js',
            ],
            'fullcalendar': [
                'https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.js',
                'https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/locales-all.js',
                'https://cdn.jsdelivr.net/npm/fullcalendar@5.11.3/main.min.css',
            ],
            'interact': [
                # 'https://cdnjs.cloudflare.com/ajax/libs/interact.js/1.0.2/interact.min.js'
                'https://cdn.jsdelivr.net/npm/interactjs@1.10.28/dist/interact.min.js'
            ],
            'timeline/': [],
            'timeline/css': [
                "https://cdn.knightlab.com/libs/timeline3/latest/css/timeline.css"],
            'timeline/css/icons/': [
                "https://cdn.knightlab.com/libs/timeline3/latest/css/icons/tl-icons.eot",
                "https://cdn.knightlab.com/libs/timeline3/latest/css/icons/tl-icons.ttf",
                "https://cdn.knightlab.com/libs/timeline3/latest/css/icons/tl-icons.svg",
                "https://cdn.knightlab.com/libs/timeline3/latest/css/icons/tl-icons.woff",
                "https://cdn.knightlab.com/libs/timeline3/latest/css/icons/tl-icons.woff2",
            ],
            'timeline/js': [
                "https://cdn.knightlab.com/libs/timeline3/latest/js/timeline.js"],
            'storymapjs': [
                "https://cdn.knightlab.com/libs/storymapjs/latest/js/storymap.js",
                "https://cdn.knightlab.com/libs/storymapjs/latest/css/storymap.css",
            ],
            'css/icons/': [
                'https://cdn.knightlab.com/libs/storymapjs/latest/css/icons/vco-icons.ttf',
                'https://cdn.knightlab.com/libs/storymapjs/latest/css/icons/vco-icons.eot',
                'https://cdn.knightlab.com/libs/storymapjs/latest/css/icons/vco-icons.woff',
                'https://cdn.knightlab.com/libs/storymapjs/latest/css/icons/vco-icons.woff2',
                'https://cdn.knightlab.com/libs/storymapjs/latest/css/icons/vco-icons.svg',
                'https://cdn.knightlab.com/libs/storymapjs/latest/css/icons/layers.png',
                'https://cdn.knightlab.com/libs/storymapjs/latest/css/icons/layers-2x.png',
            ],
            'chartjs': [
                'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/2.9.3/Chart.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/2.9.3/Chart.min.css'
            ],
            "img/": [],
            'bootstrap-tree': [
                'https://github.com/patternfly/patternfly-bootstrap-treeview/raw/v2.1.10/dist/bootstrap-treeview.min.js',
                'https://raw.githubusercontent.com/patternfly/patternfly-bootstrap-treeview/v2.1.10/dist/bootstrap-treeview.min.css'
            ],
            'tagify': [
                'https://cdn.jsdelivr.net/npm/@yaireo/tagify@4.38.0/dist/tagify.min.js',
                'https://cdn.jsdelivr.net/npm/@yaireo/tagify@4.38.0/dist/tagify.min.css'
            ],
            'grid-slider': [
                'https://cdnjs.cloudflare.com/ajax/libs/ion-rangeslider/2.3.1/js/ion.rangeSlider.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/ion-rangeslider/2.3.1/css/ion.rangeSlider.min.css'
            ],
            'sweetalert2': [
                'https://cdn.jsdelivr.net/npm/sweetalert2@11.26.25/dist/sweetalert2.all.min.js',
                'https://cdn.jsdelivr.net/npm/sweetalert2@11.26.25/dist/sweetalert2.min.css'
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
            ],
            'pdfjs': [
                'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.6.82/pdf_viewer.min.css',
                'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.6.82/pdf.min.mjs',
                'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.6.82/pdf.worker.min.mjs',
                'https://cdnjs.cloudflare.com/ajax/libs/interact.js/1.10.28/interact.min.js',
            ],

            'htmlx': [
                'https://unpkg.com/htmx.org@2.0.10/dist/htmx.min.js'
            ],
            'pdfjs/images/': [
                "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.6.82/images/messageBar_warning.svg",
                "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.6.82/images/messageBar_closingButton.svg",
                "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.6.82/images/cursor-editorInk.svg",
                "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.6.82/images/cursor-editorTextHighlight.svg",
                "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.6.82/images/cursor-editorFreeHighlight.svg",
                "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.6.82/images/altText_warning.svg",
                "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.6.82/images/cursor-editorFreeText.svg",
                "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.6.82/images/editor-toolbar-delete.svg",
                "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.6.82/images/toolbarButton-editorHighlight.svg",
                "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.6.82/images/altText_add.svg",
                "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.6.82/images/altText_done.svg",
                "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.6.82/images/altText_disclaimer.svg",
                "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.6.82/images/altText_spinner.svg",
                "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.6.82/images/toolbarButton-menuArrow.svg",
                "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.6.82/images/loading-icon.gif"
            ],
            'leaflet': [
                'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
                'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
            ],
            # leaflet.css points at images/*.png relative to itself, so these have
            # to land in the sibling folder or urlreplace cannot inline them and
            # every default marker 404s in the bundled build.
            'leaflet/images/': [
                'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
                'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
                'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
                'https://unpkg.com/leaflet@1.9.4/dist/images/layers.png',
                'https://unpkg.com/leaflet@1.9.4/dist/images/layers-2x.png',
            ],
            'leaflet-markercluster': [
                'https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css',
                'https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css',
                'https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js',
            ],
            'leaflet-heat': [
                'https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js',
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
                ]}}

        for lib in libs:
            currentbasepath = basepath / lib
            if not os.path.exists(currentbasepath):
                os.makedirs(currentbasepath)
            for staticfile in libs[lib]:
                self.get_static_file(staticfile, currentbasepath)

        for files in compressed:
            for name in compressed[files]:
                currentbasepath = basepath / files
                currentbasepath = currentbasepath / name
                self.get_static_list_file(compressed[files][name],
                                          currentbasepath)
        self.download_urls()
        self.report_checksum_mismatches()

    def report_checksum_mismatches(self):
        if not CHECKSUM_MISMATCHES:
            return
        self.stdout.write(self.style.WARNING(
            '\n%s\n%d unversioned source(s) changed since they were last '
            'vetted.\nCheck what moved, then update PINNED_CHECKSUMS in %s:\n'
            % ('=' * 78, len(CHECKSUM_MISMATCHES), Path(__file__).name)))
        for url, expected, actual in CHECKSUM_MISMATCHES:
            self.stdout.write(self.style.WARNING(
                '  %s\n    recorded %s\n    now      %s'
                % (url, expected, actual)))
