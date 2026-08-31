import hashlib
import os
import re
import shutil
from pathlib import Path
from threading import Thread, current_thread

from django.conf import settings
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

TINYMCE_VERSION = '8.8.2'
TINYMCE_URL = 'https://cdn.jsdelivr.net/npm/tinymce@%s/%%s' % TINYMCE_VERSION

# The plugins TinyMCE 8 publishes. Listed rather than discovered so a version
# bump that removes one fails loudly here instead of silently shipping a
# truncated bundle.
TINYMCE_PLUGINS = [
    'accordion', 'advlist', 'anchor', 'autolink', 'autoresize', 'autosave',
    'charmap', 'code', 'codesample', 'directionality', 'emoticons',
    'fullscreen', 'help', 'image', 'importcss', 'insertdatetime', 'link',
    'lists', 'media', 'nonbreaking', 'pagebreak', 'preview', 'quickbars',
    'save', 'searchreplace', 'table', 'visualblocks', 'visualchars',
    'wordcount',
]

MOMENT_VERSION = '2.30.1'
MOMENT_URL = 'https://cdnjs.cloudflare.com/ajax/libs/moment.js/%s/%%s' % MOMENT_VERSION

# Every locale moment 2.30.1 publishes. Kept here rather than discovered over
# the network so that a language the project declares can be matched against it
# offline, and so a language moment has no translation for is skipped instead of
# printing a FAILED line on every run.
MOMENT_LOCALES = {
    'af', 'ar', 'ar-dz', 'ar-kw', 'ar-ly', 'ar-ma', 'ar-ps', 'ar-sa', 'ar-tn',
    'az', 'be', 'bg', 'bm', 'bn', 'bn-bd', 'bo', 'br', 'bs', 'ca', 'cs', 'cv',
    'cy', 'da', 'de', 'de-at', 'de-ch', 'dv', 'el', 'en-au', 'en-ca', 'en-gb',
    'en-ie', 'en-il', 'en-in', 'en-nz', 'en-sg', 'eo', 'es', 'es-do', 'es-mx',
    'es-us', 'et', 'eu', 'fa', 'fi', 'fil', 'fo', 'fr', 'fr-ca', 'fr-ch', 'fy',
    'ga', 'gd', 'gl', 'gom-deva', 'gom-latn', 'gu', 'he', 'hi', 'hr', 'hu',
    'hy-am', 'id', 'is', 'it', 'it-ch', 'ja', 'jv', 'ka', 'kk', 'km', 'kn',
    'ko', 'ku', 'ku-kmr', 'ky', 'lb', 'lo', 'lt', 'lv', 'me', 'mi', 'mk', 'ml',
    'mn', 'mr', 'ms', 'ms-my', 'mt', 'my', 'nb', 'ne', 'nl', 'nl-be', 'nn',
    'oc-lnc', 'pa-in', 'pl', 'pt', 'pt-br', 'ro', 'ru', 'sd', 'se', 'si', 'sk',
    'sl', 'sq', 'sr', 'sr-cyrl', 'ss', 'sv', 'sw', 'ta', 'te', 'tet', 'tg',
    'th', 'tk', 'tl-ph', 'tlh', 'tr', 'tzl', 'tzm', 'tzm-latn', 'ug-cn', 'uk',
    'ur', 'uz', 'uz-latn', 'vi', 'x-pseudo', 'yo', 'zh-cn', 'zh-hk', 'zh-mo',
    'zh-tw',
}


def moment_locales():
    """The moment locale files this project can actually display.

    `moment-with-locales.min.js` put all 137 languages -- 375 KB -- into the
    bundle of every page so that one of them could be used. The core build plus
    the one locale file the page needs is 63 KB, and `get_moment_locale` links
    that file per request.

    Which ones to download comes from `settings.LANGUAGES`, so a project that
    narrowed it to its own two languages downloads two files, while one that
    never set it keeps Django's full list and loses nothing. English is not
    among them: it is built into moment's core build.
    """
    dev = []
    for code, _name in settings.LANGUAGES:
        code = code.lower()
        # A regional code moment does not carry (Django's 'es-ar') falls back
        # to its base language ('es') rather than to English.
        for candidate in (code, code.split('-')[0]):
            if candidate in ('en', 'en-us'):
                break
            if candidate in MOMENT_LOCALES:
                if candidate not in dev:
                    dev.append(candidate)
                break
    return dev


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
            # 3.1.0 is the last release and it is only published to npm, which
            # ships the sources unminified; jsDelivr minifies them on request, so
            # the vendored file names stay the ones pylpfile.py and the templates
            # already reference. The moment.min.js this package carries is not
            # downloaded: moment comes from its own entry below and no template
            # ever linked the copy.
            'bootstrap-daterangepicker': [
                'https://cdn.jsdelivr.net/npm/daterangepicker@3.1.0/daterangepicker.min.js',
                'https://cdn.jsdelivr.net/npm/daterangepicker@3.1.0/daterangepicker.min.css',
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
            'nprogress': [
                'https://cdnjs.cloudflare.com/ajax/libs/nprogress/0.2.0/nprogress.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/nprogress/0.2.0/nprogress.min.css',
                # 'https://cdnjs.cloudflare.com/ajax/libs/nprogress/0.2.0/nprogress.min.js',
                # 'https://cdnjs.cloudflare.com/ajax/libs/nprogress/0.2.0/nprogress.min.css',
            ],
            'jquery': [
                'https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.1/jquery.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.1/jquery.min.map',
                # 'https://cdnjs.cloudflare.com/ajax/libs/jquery/2.2.3/jquery.min.js',
                # 'https://cdnjs.cloudflare.com/ajax/libs/jquery/2.2.3/jquery.min.map'
            ],
            # The jQuery build is a superset of inputmask.min.js -- both dist
            # files carry the whole library -- and every call site here goes
            # through $(el).inputmask(), so only this one is downloaded.
            'inputmask': [
                'https://cdn.jsdelivr.net/npm/inputmask@5.0.10/dist/'
                'jquery.inputmask.min.js',
            ],
            'moment': [
                MOMENT_URL % 'moment.min.js',
            ],
            'moment/locale': [
                MOMENT_URL % ('locale/%s.js' % code)
                for code in moment_locales()
            ],
            'autosize': [
                'https://cdnjs.cloudflare.com/ajax/libs/autosize.js/6.0.1/autosize.min.js'
            ],
            'bootstrap-maxlength': [
                'https://cdn.jsdelivr.net/npm/bootstrap-maxlength@2.0.0/dist/'
                'bootstrap-maxlength.min.js',
            ],
            # A combined build with the three extensions this project uses:
            # Buttons (as the toolbar for the actions, never for exporting),
            # ColReorder and Responsive. The 1.12 build also carried AutoFill,
            # DateTime, FixedColumns, FixedHeader, KeyTable, RowGroup,
            # RowReorder, Scroller, SearchBuilder, SearchPanes, Select,
            # StateRestore, jszip and the colvis/html5/print buttons -- 500 KB
            # with not one reference anywhere in the project. Row selection is
            # hand rolled with .gtcheckable checkboxes, not the Select
            # extension. Rebuild the URL at https://datatables.net/download.
            'datatables': [
                'https://cdn.datatables.net/v/bs5/dt-2.3.7/b-3.2.6/cr-2.1.2/'
                'r-3.0.7/datatables.min.js',
                'https://cdn.datatables.net/v/bs5/dt-2.3.7/b-3.2.6/cr-2.1.2/'
                'r-3.0.7/datatables.min.css',
                'https://cdn.datatables.net/plug-ins/2.3.7/i18n/en-GB.json',
                'https://cdn.datatables.net/plug-ins/2.3.7/i18n/es-ES.json',
            ],
            # What is left of the upload group. blueimp jQuery-File-Upload went
            # with the rewrite in js/base/chunkedupload.js, and with it the
            # jQuery UI widget factory it was built on and an iframe transport
            # for browsers with no XHR file upload -- that is, IE9. spark-md5
            # stays because it does the one thing the platform cannot: hash a
            # file incrementally, so a large upload is never held in memory.
            'fileupload': [
                'https://cdnjs.cloudflare.com/ajax/libs/spark-md5/3.0.2/'
                'spark-md5.min.js',
            ],
            # FullCalendar 6 ships one global build with the standard plugins
            # already in it, and no stylesheet at all: it injects its own CSS
            # from javascript, so there is nothing left to link or to bundle.
            # (locales-all.js is not downloaded any more either -- it moved to
            # another package in 6, and no template ever loaded it.)
            'fullcalendar': [
                'https://cdn.jsdelivr.net/npm/fullcalendar@6.1.20/'
                'index.global.min.js',
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
            # Chart.js 3 dropped the stylesheet -- everything the old Chart.min.css
            # styled is drawn on the canvas now -- and renamed the browser build
            # to chart.umd.js.
            'chartjs': [
                'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.1/'
                'chart.umd.min.js',
            ],
            "img/": [],
            'tagify': [
                'https://cdn.jsdelivr.net/npm/@yaireo/tagify@4.38.0/dist/tagify.min.js',
                'https://cdn.jsdelivr.net/npm/@yaireo/tagify@4.38.0/dist/tagify.min.css'
            ],
            'grid-slider': [
                'https://cdn.jsdelivr.net/npm/ion-rangeslider@2.3.2/js/ion.rangeSlider.min.js',
                'https://cdn.jsdelivr.net/npm/ion-rangeslider@2.3.2/css/ion.rangeSlider.min.css'
            ],
            'sweetalert2': [
                'https://cdn.jsdelivr.net/npm/sweetalert2@11.26.25/dist/sweetalert2.all.min.js',
                'https://cdn.jsdelivr.net/npm/sweetalert2@11.26.25/dist/sweetalert2.min.css'
            ],
            # TinyMCE 8. Two things moved since the 5.6.1 this replaced:
            # jquery.tinymce.min.js is no longer part of the package (the jQuery
            # integration became a separate project, and the call sites use
            # tinymce.init() instead), and models/dom/model.min.js is new and
            # mandatory -- without it the editor does not start.
            'tinymce': [
                TINYMCE_URL % 'tinymce.min.js',
            ],
            'tinymce/themes/silver': [
                TINYMCE_URL % 'themes/silver/theme.min.js',
            ],
            'tinymce/models/dom': [
                TINYMCE_URL % 'models/dom/model.min.js',
            ],
            'tinymce/skins/content/dark/': [
                TINYMCE_URL % 'skins/content/dark/content.min.css',
            ],
            'tinymce/skins/content/default/': [
                TINYMCE_URL % 'skins/content/default/content.min.css',
            ],
            'tinymce/skins/content/document': [
                TINYMCE_URL % 'skins/content/document/content.min.css',
            ],
            'tinymce/skins/content/writer': [
                TINYMCE_URL % 'skins/content/writer/content.min.css',
            ],
            # The *.mobile.min.css of the 5.x skins are gone: so is the mobile
            # theme they styled.
            'tinymce/skins/ui/oxide-dark/': [
                TINYMCE_URL % 'skins/ui/oxide-dark/content.inline.min.css',
                TINYMCE_URL % 'skins/ui/oxide-dark/content.min.css',
                TINYMCE_URL % 'skins/ui/oxide-dark/skin.min.css',
                TINYMCE_URL % 'skins/ui/oxide-dark/skin.shadowdom.min.css',
            ],
            'tinymce/skins/ui/oxide/': [
                TINYMCE_URL % 'skins/ui/oxide/content.inline.min.css',
                TINYMCE_URL % 'skins/ui/oxide/content.min.css',
                TINYMCE_URL % 'skins/ui/oxide/skin.min.css',
                TINYMCE_URL % 'skins/ui/oxide/skin.shadowdom.min.css',
            ],
            'storylinejs': [
                'https://cdn.knightlab.com/libs/storyline/1.1.0/css/storyline.css',
                'https://cdn.knightlab.com/libs/storyline/1.1.0/js/storyline.js',
            ],
            'pdfjs': [
                # pdf_viewer.css is not downloaded: it styles the text,
                # annotation and XFA layers, and nothing here renders one --
                # both the signature widget and the shelved viewer draw straight
                # to a canvas through getDocument/getViewport/render. It took
                # the whole images/ directory with it, which existed only to
                # feed its url()s.
                'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/6.2.108/pdf.min.mjs',
                'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/6.2.108/pdf.worker.min.mjs',
            ],

            'htmx': [
                'https://unpkg.com/htmx.org@2.0.10/dist/htmx.min.js'
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
        # Every plugin the build ships, concatenated into one file loaded
        # after tinymce.min.js: each of them only registers itself with the
        # PluginManager, so a project enables what it wants through `plugins`
        # without a second round trip. The 5.x list had 46 entries; 15 of those
        # plugins no longer exist -- paste, print, hr, colorpicker, contextmenu,
        # textcolor, noneditable and tabfocus were absorbed into the core,
        # bbcode, legacyoutput, spellchecker and textpattern were dropped, and
        # fullpage, imagetools, template and toc became premium.
        compressed = {
            'tinymce': {
                'tinymce-all.js': [
                    TINYMCE_URL % 'icons/default/icons.min.js',
                ] + [
                    TINYMCE_URL % ('plugins/%s/plugin.min.js' % plugin)
                    for plugin in TINYMCE_PLUGINS
                ] + [
                    # The emoji database the emoticons plugin looks up.
                    TINYMCE_URL % 'plugins/emoticons/js/emojis.min.js',
                ],
                'skin.min.css': [
                    TINYMCE_URL % 'skins/ui/oxide/skin.min.css',
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
