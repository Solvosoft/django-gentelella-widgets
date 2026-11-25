"""The registry of menu widgets (W20).

On 4faeda00 a ``MenuItem`` with ``is_widget`` made the menu tags run
``import_string(item.url_name)(context).render()``: whoever could edit a menu
item made every page import and call any class of the project.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings

from demoapp.menu_widgets import UserBadgeMenu
from djgentelella import menu
from djgentelella.admin import MenuItemForm
from djgentelella.menu import (
    get_menu_widget, is_menu_widget, menu_widget_name, register_menu_widget,
    registered_menu_widgets,
)
from djgentelella.models import MenuItem

TOP = Template('{% load gentelellamenu %}{% top_menu %}')
FOOTER = Template('{% load gentelellamenu %}{% footer_sidebar_menu %}')


class Unregistered:
    """A class with a ``render``, importable, that nobody declared."""

    built = 0

    def __init__(self, context):
        type(self).built += 1

    def render(self):
        return '<span>unregistered widget</span>'


@register_menu_widget
class Registered:
    def __init__(self, context):
        self.context = context

    def render(self):
        return '<span>registered widget</span>'

    def get_title(self, item):
        return 'registered title'


@register_menu_widget(name='w20-short-name')
class Named(Registered):
    def render(self):
        return '<span>named widget</span>'


class FromSettings(Registered):
    def render(self):
        return '<span>widget of the settings</span>'


def path(cls):
    return '%s.%s' % (__name__, cls.__name__)


class MenuWidgetRegistryTests(TestCase):
    def setUp(self):
        Unregistered.built = 0
        menu._warned.clear()
        self.user = get_user_model().objects.create_user('menu-w20')

    def render(self, template=TOP):
        request = RequestFactory().get('/')
        request.user = self.user
        return template.render(Context({'request': request}))

    def widget_item(self, cls_path, category='main', title='Widget item'):
        return MenuItem.objects.create(title=title, url_name=cls_path,
                                       category=category, is_widget=True)

    def test_an_unregistered_widget_is_not_built(self):
        # The reproduction: on 4faeda00 the class was imported and built.
        self.widget_item(path(Unregistered))
        MenuItem.objects.create(title='Plain', url_name='/plain', category='main')
        with self.assertLogs('djgentelella.menu', 'WARNING') as logs:
            html = self.render()
        self.assertEqual(Unregistered.built, 0)
        self.assertNotIn('unregistered widget', html)
        self.assertNotIn('Widget item', html)
        self.assertIn('Plain', html)
        self.assertIn('is not registered', logs.output[0])

    def test_an_unregistered_widget_in_the_footer(self):
        self.widget_item(path(Unregistered), category='sidebarfooter')
        with self.assertLogs('djgentelella.menu', 'WARNING'):
            html = self.render(FOOTER)
        self.assertEqual(Unregistered.built, 0)
        self.assertNotIn('fsb_', html)

    def test_a_path_that_is_not_a_widget_is_never_imported(self):
        self.widget_item('os.system')
        with self.assertLogs('djgentelella.menu', 'WARNING'):
            self.assertEqual(self.render().strip(), '')

    def test_the_warning_is_logged_once_per_name(self):
        with self.assertLogs('djgentelella.menu', 'WARNING') as logs:
            self.assertIsNone(get_menu_widget(path(Unregistered)))
            self.assertIsNone(get_menu_widget(path(Unregistered)))
        self.assertEqual(len(logs.output), 1)

    def test_a_registered_widget_renders(self):
        self.widget_item(path(Registered))
        self.assertIn('registered widget', self.render())
        self.widget_item(path(Registered), category='sidebarfooter')
        self.assertIn('registered title', self.render(FOOTER))

    def test_by_its_path_and_by_its_name(self):
        self.assertIs(get_menu_widget(path(Named)), Named)
        self.assertIs(get_menu_widget('w20-short-name'), Named)
        self.assertEqual(menu_widget_name(Named), path(Named))
        self.widget_item('w20-short-name')
        self.assertIn('named widget', self.render())

    def test_the_widgets_of_djgentelella_register_themselves(self):
        widgets = registered_menu_widgets()
        self.assertIn('djgentelella.menu_widgets.palette.PalleteWidget', widgets)
        self.assertIn('djgentelella.notification.widgets.NotificationMenu', widgets)

    def test_a_class_of_the_menu_widgets_module_of_an_app(self):
        self.assertIs(get_menu_widget('demoapp.menu_widgets.UserBadgeMenu'),
                      UserBadgeMenu)
        # What the module only imports is not one of its widgets.
        with self.assertLogs('djgentelella.menu', 'WARNING'):
            self.assertIsNone(get_menu_widget('demoapp.menu_widgets.format_html'))
        self.widget_item('demoapp.menu_widgets.UserBadgeMenu')
        self.assertIn('menu-w20', self.render())

    def test_listed_in_the_settings(self):
        with self.assertLogs('djgentelella.menu', 'WARNING'):
            self.assertFalse(is_menu_widget(path(FromSettings)))
        with override_settings(GT_MENU_WIDGETS=[path(FromSettings)]):
            self.assertTrue(is_menu_widget(path(FromSettings)))
            self.assertIn(path(FromSettings), registered_menu_widgets())
            self.widget_item(path(FromSettings))
            self.assertIn('widget of the settings', self.render())

    def test_the_model_refuses_an_unregistered_widget(self):
        item = MenuItem(title='Bad', url_name=path(Unregistered), is_widget=True)
        with self.assertLogs('djgentelella.menu', 'WARNING'):
            with self.assertRaises(ValidationError) as caught:
                item.full_clean()
        self.assertIn('url_name', caught.exception.message_dict)
        MenuItem(title='Good', url_name=path(Registered), is_widget=True).full_clean()
        # A plain link is not a widget, whatever it names.
        MenuItem(title='Link', url_name=path(Unregistered)).full_clean()

    def test_the_admin_form_refuses_it(self):
        data = {'title': 'Bad', 'url_name': path(Unregistered), 'category': 'main',
                'is_widget': 'on', 'position': 0}
        with self.assertLogs('djgentelella.menu', 'WARNING'):
            form = MenuItemForm(data)
            self.assertFalse(form.is_valid())
        self.assertIn('url_name', form.errors)
