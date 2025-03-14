import base64
import re
from pathlib import Path

import pylp
from css_html_js_minify import css_minify, js_minify
from pylpconcat import concat


##
##  pip install pylp pylpconcat css-html-js-minify
##


class urlreplace(pylp.Transformer):
    data_header = {
        '.eot': 'data:application/x-font-eot;base64,',
        '.svg': 'data:image/svg+xml;charset=utf-8;base64,',
        '.png': 'data:image/png;charset=utf-8;base64,',
        '.woff': 'data:application/font-woff;charset=utf-8;base64,',
        '.woff2': 'data:application/font-woff2;charset=utf-8;base64,',
        '.ttf': 'data:application/x-font-truetype;charset=utf-8;base64,',
    }

    def check_url(self, url):
        if 'data:' in url or '#default#VML' in url:
            return False
        # print(url)
        return True

    def extract_url(self, url):
        if 'storymapjs' in url:
            print(url)
        url = url.replace("url(", '').replace(
            ")", '').replace("'", '').replace('"', "").split('?')[0]
        return url.split("#")[0]

    def get_file_content(self, file, url):
        if self.check_url(url):
            fpath = Path(file.path).parent / self.extract_url(url)
            content = ""
            if fpath.suffix in self.data_header:
                content = self.data_header[fpath.suffix]
            try:
                with open(fpath, 'rb') as arch:
                    content += base64.b64encode(arch.read()).decode()
            except:
                print("This is an ERROR,  Not Found : ", file.path, url)
            return "url('" + content + "')"

    # Function called when a file need to be transformed
    async def transform(self, file):
        re_expr = r"""url\(['|"]\.[^'|"]+['|"]\)"""
        re_expr = r"""url\([^\)]+\)"""
        urls = re.findall(re_expr, file.contents)
        if urls:
            for url in urls:
                content = self.get_file_content(file, url)
                if content:
                    file.contents = file.contents.replace(url, content)
        return file


class cssminify(pylp.Transformer):
    async def transform(self, file):
        file.contents = css_minify(file.contents, comments=False)
        return file


class jsminify(pylp.Transformer):
    async def transform(self, file):
        file.contents = js_minify(file.contents)
        return file


BASE_PATH = Path('./djgentelella/static/')

CSS_FILES = [str(BASE_PATH / path) for path in [
    'vendors/bootstrap/bootstrap.min.css',
    'vendors/font-awesome/font-awesome.min.css',
    'vendors/bootstrap-daterangepicker/daterangepicker.min.css',
    'vendors/bootstrap-datetimepicker/bootstrap-datetimepicker.min.css',
    'vendors/select2/select2.min.css',
    'vendors/select2/select2-bootstrap-5-theme.min.css',
    'vendors/switchery/switchery.min.css',
    'vendors/iCheck/green.css',
    'vendors/bootstrap-progressbar/bootstrap-progressbar-3.3.4.min.css',
    'vendors/nprogress/nprogress.min.css',
    'vendors/tagify/tagify.min.css',
    'vendors/grid-slider/ion.rangeSlider.min.css',
    'vendors/sweetalert2/sweetalert2.min.css',
    'vendors/chartjs/Chart.min.css',
    'vendors/datatables/datatables.min.css',
    'vendors/pdfjs/pdf_viewer.min.css'
]]

READONLY_WIDGETS_CSS = [str(BASE_PATH / path) for path in [
    'vendors/timeline/css/timeline.css',
    'vendors/fullcalendar/main.min.css',
    'vendors/storymapjs/storymap.css',
    'vendors/storylinejs/storyline.css',
]]

FLAGS_CSS = [str(BASE_PATH / path) for path in [
    'vendors/flag-icon-css/flag-icons.min.css',
]]

JS_FILES_HEADER = [str(BASE_PATH / path) for path in [
    'vendors/jquery/jquery.min.js',
    'vendors/friconix/friconix.js',
    'vendors/bootstrap/popper.min.js',
    'vendors/bootstrap/bootstrap.min.js'
]]

JS_FILES = [str(BASE_PATH / path) for path in [
    'vendors/squirrelly/squirrelly.min.js',
    'vendors/moment/moment-with-locales.min.js',
    'vendors/jquery-knob/jquery.knob.min.js',
    'vendors/inputmask/inputmask.min.js',
    'vendors/inputmask/jquery.inputmask.min.js',
    'vendors/nprogress/nprogress.min.js',
    'vendors/bootstrap-progressbar/bootstrap-progressbar.min.js',
    'vendors/iCheck/icheck.min.js',
    'vendors/interact/interact.min.js',
    'vendors/bootstrap-daterangepicker/daterangepicker.min.js',
    'vendors/bootstrap-datetimepicker/bootstrap-datetimepicker.min.js',
    'vendors/switchery/switchery.min.js',
    'vendors/select2/select2.min.js',
    'vendors/parsleyjs/parsley.min.js',
    'vendors/autosize/autosize.min.js',
    'vendors/bootstrap-maxlength/bootstrap-maxlength.min.js',
    'vendors/fileupload/jquery.ui.widget.min.js',
    'vendors/grid-slider/ion.rangeSlider.min.js',
    'vendors/fileupload/jquery.iframe-transport.min.js',
    'vendors/fileupload/jquery.fileupload.min.js',
    'vendors/fileupload/spark-md5.min.js',
    'vendors/tagify/tagify.min.js',
    'vendors/sweetalert2/sweetalert2.all.min.js',
    'vendors/datatables/datatables.min.js',
    'vendors/chartjs/Chart.min.js',
    'vendors/pdfjs/interact.min.js',
    'vendors/htmlx/htmx.min.js',
]]

READONLY_WIDGETS_JS = [str(BASE_PATH / path) for path in [
    'vendors/timeline/js/timeline.js',
    'vendors/fullcalendar/main.min.js',
    'vendors/storymapjs/storymap.js',
    'vendors/storylinejs/storyline.js',
    'vendors/bootstrap-tree/bootstrap-treeview.min.js'
]]

pylp.task('css', lambda:
pylp.src(CSS_FILES)
          .pipe(urlreplace())
          .pipe(concat('djgentelella.vendors.min.css'))
          .pipe(pylp.dest(str(BASE_PATH)))
          )
pylp.task('readonlycss', lambda:
pylp.src(READONLY_WIDGETS_CSS)
          .pipe(urlreplace())
          .pipe(concat('djgentelella.readonly.vendors.min.css'))
          .pipe(pylp.dest(str(BASE_PATH)))
          )

pylp.task('flagcss', lambda: pylp.src(FLAGS_CSS)
          .pipe(urlreplace())
          .pipe(concat('djgentelella.flags.vendors.min.css'))
          .pipe(pylp.dest(str(BASE_PATH)))
          )

pylp.task('jsheader', lambda:
pylp.src(JS_FILES_HEADER)
          .pipe(concat('djgentelella.vendors.header.min.js'))
          .pipe(pylp.dest(str(BASE_PATH)))
          )

pylp.task('js', lambda:
pylp.src(JS_FILES)
          .pipe(concat('djgentelella.vendors.min.js'))
          .pipe(pylp.dest(str(BASE_PATH)))
          )

pylp.task('readonlyjs', lambda:
pylp.src(READONLY_WIDGETS_JS)
          .pipe(concat('djgentelella.readonly.vendors.min.js'))
          .pipe(pylp.dest(str(BASE_PATH)))
          )
pylp.task('default', ['css', 'flagcss', 'readonlycss', 'jsheader', 'js', 'readonlyjs'])
# pylp.task('default', ['flagcss'])
