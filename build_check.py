"""Verify that the built wheel carries everything djgentelella needs at runtime.

Python modules are found by ``[tool.setuptools.packages.find]``, but templates,
static files and translations only reach the package through ``MANIFEST.in``,
where a missing line is invisible until an installed copy raises
``TemplateDoesNotExist``. This compares the wheel against the working tree and
fails the build when a tree is absent or came out short.

Run through ``make check-dist`` (also a prerequisite of ``make release``).
"""
import glob
import re
import sys
import zipfile
from pathlib import Path

PACKAGE = Path('djgentelella')

# Directory trees the package cannot work without. Each is checked for presence
# and for carrying every file the working tree has.
REQUIRED_TREES = [
    'templates',
    'static/gentelella',
    'locale',
    'blog/templates',
    'blog/static',
    'async_notification/templates',
    'async_notification/static',
]

# Built at release time by `make sdist`, so they are absent from a bare build.
# Everything the base templates load: they live straight under static/, which no
# REQUIRED_TREES entry covers, and the generated ones are gitignored -- a wheel
# built without running pylp looks complete and 404s on every page.
BUNDLED_ARTIFACTS = [
    # gentelella/statics/javascript_header.html + javascript.html
    'static/djgentelella.vendors.header.min.js',
    'static/djgentelella.vendors.min.js',
    'static/djgentelella.readonly.vendors.min.js',
    'static/gentelella/js/base.js',
    # gentelella/statics/stylesheets.html
    'static/djgentelella.vendors.min.css',
    'static/djgentelella.readonly.vendors.min.css',
    'static/djgentelella.flags.vendors.min.css',
    # compilemessages: django.po drives python/templates, djangojs.po the widgets
    'locale/es/LC_MESSAGES/django.mo',
    'locale/es/LC_MESSAGES/djangojs.mo',
]


def tree_files(tree):
    root = PACKAGE / tree
    if not root.is_dir():
        return set()
    return {
        path.relative_to(PACKAGE).as_posix()
        for path in root.rglob('*')
        if path.is_file() and not path.name.endswith(('.pyc', '~'))
    }


def the_wheel():
    """The one wheel to check, refusing to guess between several.

    `make release` uploads dist/* wholesale, so a leftover from an earlier
    version is not a harmless stale file: it would be published alongside the
    real one. `make sdist` cleans dist/ first; this catches the case where it
    did not.
    """
    wheels = glob.glob('dist/*.whl')
    if not wheels:
        sys.exit('no wheel in dist/ -- run `make sdist` first')
    if len(wheels) > 1:
        sys.exit('dist/ holds %d wheels, and `make release` would upload all '
                 'of them:\n  %s\nrun `make clean-build` and rebuild.' % (
                     len(wheels), '\n  '.join(sorted(wheels))))
    return wheels[0]


def declared_version():
    """The version `make release` is about to tag, read the way setup does."""
    source = (PACKAGE / '__init__.py').read_text()
    match = re.search(r'''__version__\s*=\s*['"]([^'"]+)['"]''', source)
    if not match:
        sys.exit('no __version__ in %s' % (PACKAGE / '__init__.py'))
    return match.group(1)


def main():
    wheel = the_wheel()
    # `make release` tags from djgentelella/__init__.py but uploads whatever is
    # in dist/, which `make check-dist` does not rebuild. A wheel left over from
    # the previous version would be published under the new tag.
    version = declared_version()
    wheel_version = Path(wheel).name.split('-')[1]
    if wheel_version != version:
        sys.exit('%s holds version %s but djgentelella/__init__.py declares %s '
                 '-- run `make sdist` to rebuild.' % (
                     wheel, wheel_version, version))

    shipped = {
        name[len('djgentelella/'):]
        for name in zipfile.ZipFile(wheel).namelist()
        if name.startswith('djgentelella/')
    }

    problems = []
    for tree in REQUIRED_TREES:
        expected = tree_files(tree)
        if not expected:
            problems.append('%s is missing from the working tree' % tree)
            continue
        missing = expected - shipped
        if missing:
            problems.append('%s: %d of %d files not in the wheel (e.g. %s)' % (
                tree, len(missing), len(expected), sorted(missing)[0]))

    for artifact in BUNDLED_ARTIFACTS:
        if artifact not in shipped:
            problems.append('%s not in the wheel -- did pylp / createbasejs / '
                            'compilemessages run?' % artifact)

    # `graft djgentelella` in MANIFEST.in sweeps up test suites too, and
    # include-package-data puts them in the wheel whatever packages.find
    # excludes. They import the demo project, so an installed copy cannot even
    # import them. Each tests/ tree needs its own `prune` line; this catches the
    # one a new module forgets.
    tests = sorted({name.split('/tests/')[0] + '/tests'
                    for name in shipped if '/tests/' in name})
    if tests:
        problems.append('test modules in the wheel (they import the demo '
                        'project and cannot be imported once installed) -- add '
                        '`prune djgentelella/...` to MANIFEST.in for: %s'
                        % ', '.join(tests))

    print('checking %s (version %s, %d files under djgentelella/)' % (
        wheel, version, len(shipped)))
    if problems:
        for problem in problems:
            print('  FAIL  %s' % problem)
        sys.exit(1)
    for tree in REQUIRED_TREES:
        print('  ok    %s (%d files)' % (tree, len(tree_files(tree))))
    print('  ok    bundled artifacts')


if __name__ == '__main__':
    main()
