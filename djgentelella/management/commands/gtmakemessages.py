"""``makemessages`` that finds every ``djangojs`` string of djgentelella.

xgettext only reads ``.js`` files and only knows ``gettext`` and its
siblings, so two kinds of strings never reach ``djangojs.po`` with the plain
command, and ``--no-obsolete`` then deletes their translations:

* the ``pg_gettext(...)`` calls of ``positionsgrid.js``, a wrapper that works
  without the javascript catalog: one more keyword here;
* the ``gettext(...)`` calls of the inline ``<script>`` blocks of templates.
  For the ``djangojs`` domain each template with one is copied, while the
  command runs, to ``gt_template_scripts/<path>.js`` with only its scripts
  -- every other line left blank and template tags blanked, so the line
  numbers still match -- and the locations written in the catalog point back
  at the template.

The ``django`` domain is the plain ``makemessages``. ``make messages`` runs it
from the ``djgentelella`` directory.
"""

import re
import shutil
from fnmatch import fnmatchcase
from pathlib import Path

from django.core.management.commands import makemessages

#: Where the scripts of the templates are copied, under the current directory.
SCRIPTS_DIR = 'gt_template_scripts'
#: An inline script: no ``src``.
INLINE_SCRIPT = re.compile(r'(<script(?![^>]*\bsrc\s*=)[^>]*>)(.*?)</script>',
                           re.DOTALL | re.IGNORECASE)
TEMPLATE_CODE = re.compile(r'{%.*?%}|{{.*?}}|{#.*?#}', re.DOTALL)


def blank(text):
    """``text`` with every character but the newlines turned into spaces."""
    return re.sub(r'[^\n]', ' ', text)


def template_scripts(source):
    """The inline scripts of a template, at their own lines, or ``''``.

    Template tags become ``0`` padded to their length (or spaces, when they
    span lines), so the javascript around them still parses.
    """
    parts, last, found = [], 0, False
    for match in INLINE_SCRIPT.finditer(source):
        found = True
        parts.append(blank(source[last:match.start(2)]))
        parts.append(TEMPLATE_CODE.sub(
            lambda tag: blank(tag.group()) if '\n' in tag.group()
            else '0'.ljust(len(tag.group())), match.group(2)))
        last = match.end(2)
    if not found:
        return ''
    parts.append(blank(source[last:]))
    return ''.join(parts)


class Command(makemessages.Command):
    help = (makemessages.Command.help + ' For djangojs, pg_gettext() is a keyword '
            'and the inline <script> blocks of templates are read too.')

    def handle(self, *args, **options):
        if options.get('domain') != 'djangojs':
            return super().handle(*args, **options)
        self.xgettext_options = self.xgettext_options + ['--keyword=pg_gettext']
        root = Path.cwd()
        target = root / SCRIPTS_DIR
        if target.exists():
            shutil.rmtree(target)
        try:
            self.copy_scripts(root, target, options.get('ignore_patterns') or [])
            result = super().handle(*args, **options)
        finally:
            shutil.rmtree(target, ignore_errors=True)
        self.point_at_templates(root)
        return result

    def copy_scripts(self, root, target, ignore_patterns):
        """Copy the scripts of the templates under ``root`` that no
        ``--ignore`` pattern leaves out."""
        for template in sorted(root.glob('**/templates/**/*.html')):
            relative = template.relative_to(root)
            if relative.parts[0] == SCRIPTS_DIR or any(
                    fnmatchcase(str(path), pattern) for pattern in ignore_patterns
                    for path in [relative, *relative.parents]):
                continue
            scripts = template_scripts(template.read_text(encoding='utf-8'))
            if scripts.strip():
                copy = target / relative.with_name(relative.name + '.js')
                copy.parent.mkdir(parents=True, exist_ok=True)
                copy.write_text(scripts, encoding='utf-8')

    def point_at_templates(self, root):
        """``gt_template_scripts/<path>.html.js:<line>`` -> ``<path>.html:<line>``."""
        pattern = re.compile(r'%s/(\S+?\.html)\.js' % re.escape(SCRIPTS_DIR))
        for catalog in root.glob('locale/*/LC_MESSAGES/djangojs.po'):
            text = catalog.read_text(encoding='utf-8')
            fixed = pattern.sub(r'\1', text)
            if fixed != text:
                catalog.write_text(fixed, encoding='utf-8')
