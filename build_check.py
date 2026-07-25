"""Verify that the built wheel carries everything djgentelella needs at runtime.

Python modules are found by ``[tool.setuptools.packages.find]``, but templates,
static files and translations only reach the package through ``MANIFEST.in``,
where a missing line is invisible until an installed copy raises
``TemplateDoesNotExist``. This compares the wheel against the working tree and
fails the build when a tree is absent or came out short.

Run through ``make check-dist`` (also a prerequisite of ``make release``).
"""
import glob
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
BUNDLED_ARTIFACTS = [
    'static/djgentelella.vendors.min.js',
    'static/djgentelella.vendors.min.css',
    'static/gentelella/js/base.js',
    'locale/es/LC_MESSAGES/django.mo',
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


def main():
    wheel = the_wheel()
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

    print('checking %s (%d files under djgentelella/)' % (wheel, len(shipped)))
    if problems:
        for problem in problems:
            print('  FAIL  %s' % problem)
        sys.exit(1)
    for tree in REQUIRED_TREES:
        print('  ok    %s (%d files)' % (tree, len(tree_files(tree))))
    print('  ok    bundled artifacts')


if __name__ == '__main__':
    main()
