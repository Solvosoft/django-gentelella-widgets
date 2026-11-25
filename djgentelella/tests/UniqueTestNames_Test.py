"""``tests/__init__.py`` imports every module with ``*``: two classes with the
same name in two modules leave only the last one in the package, and the test
runner never sees the first. Nothing fails; its tests just stop running.

These checks fail instead: a class of a test module whose name another module
also exports, a test case a module defines but does not export (a stale
``__all__``) and a ``*_Test.py`` that ``__init__.py`` does not import.
"""

import ast
import importlib
import inspect
import types
import unittest
from pathlib import Path

from django.test import SimpleTestCase

PACKAGE = 'djgentelella.tests'
HERE = Path(__file__).resolve().parent


def star_imports(init_file=HERE / '__init__.py'):
    """The modules ``__init__.py`` imports with ``from .<module> import *``,
    in order."""
    tree = ast.parse(Path(init_file).read_text())
    return [node.module for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.level == 1
            and any(alias.name == '*' for alias in node.names)]


def exported(module):
    """The names ``from module import *`` binds."""
    names = getattr(module, '__all__', None)
    if names is None:
        names = [name for name in vars(module) if not name.startswith('_')]
    return list(names)


def own_classes(module, prefix=PACKAGE):
    """``{name: class}`` of the classes ``module`` exports that a test module
    defines (imported helpers of other test modules count too: the same
    object exported twice is not a clash)."""
    found = {}
    for name in exported(module):
        value = getattr(module, name, None)
        if inspect.isclass(value) and value.__module__.startswith(prefix):
            found[name] = value
    return found


def duplicate_names(modules, prefix=PACKAGE):
    """``[(name, first module, later module)]``: the classes the later module
    hides from the package namespace."""
    seen, clashes = {}, []
    for module in modules:
        for name, value in own_classes(module, prefix).items():
            if name in seen and seen[name][1] is not value:
                clashes.append((name, seen[name][0], module.__name__))
            seen[name] = (module.__name__, value)
    return clashes


def has_tests(test_case):
    loader = unittest.TestLoader()
    return bool(loader.getTestCaseNames(test_case))


def unexported_tests(module):
    """Test cases with tests that ``module`` defines and ``import *`` would
    not bring (a base class without tests may stay out of ``__all__``)."""
    names = set(exported(module))
    return [name for name, value in vars(module).items()
            if inspect.isclass(value) and issubclass(value, unittest.TestCase)
            and value.__module__ == module.__name__ and name not in names
            and not name.startswith('_') and has_tests(value)]


class UniqueTestNamesTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.modules = [importlib.import_module('%s.%s' % (PACKAGE, name))
                       for name in star_imports()]

    def test_no_class_name_is_exported_by_two_modules(self):
        clashes = duplicate_names(self.modules)
        self.assertEqual(clashes, [], 'a class of a later module hides the '
                         'one of an earlier module: rename one of them')

    def test_every_test_case_is_exported(self):
        missing = {module.__name__: unexported_tests(module)
                   for module in self.modules if unexported_tests(module)}
        self.assertEqual(missing, {}, 'add these to the __all__ of the module')

    def test_every_test_module_is_imported(self):
        files = {path.stem for path in HERE.glob('*_Test.py')}
        self.assertEqual(sorted(files - set(star_imports())), [])

    def test_the_check_finds_a_duplicate(self):
        def module(name, **classes):
            item = types.ModuleType('%s.%s' % (PACKAGE, name))
            for class_name, base in classes.items():
                setattr(item, class_name, type(class_name, (base,), {
                    '__module__': item.__name__}))
            return item

        first = module('First_Test', SchemaTests=SimpleTestCase, Form=object)
        second = module('Second_Test', SchemaTests=SimpleTestCase)
        shared = module('Third_Test')
        shared.Form = first.Form  # the same helper imported: not a clash
        self.assertEqual(duplicate_names([first, second, shared]), [
            ('SchemaTests', PACKAGE + '.First_Test', PACKAGE + '.Second_Test')])
        self.assertEqual(duplicate_names([first, shared]), [])

    def test_the_check_finds_a_stale_all(self):
        item = types.ModuleType(PACKAGE + '.Stale_Test')

        def case(name):
            return type(name, (SimpleTestCase,), {
                '__module__': item.__name__, 'test_it': lambda self: None})

        item.KeptTests, item.LostTests = case('KeptTests'), case('LostTests')
        item.BaseCase = type('BaseCase', (SimpleTestCase,),
                             {'__module__': item.__name__})
        item.__all__ = ['KeptTests']
        self.assertEqual(unexported_tests(item), ['LostTests'])

    def test_the_imports_are_read_in_order(self):
        self.assertEqual(star_imports()[:2], ['BreadcrumbNav_Test', 'Calendar_Test'])
