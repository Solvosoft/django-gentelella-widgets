from random import randint

from django.core.management import BaseCommand
from django.urls import reverse
from django.utils.timezone import now

from demoapp.models import Country, Person
from djgentelella.models import MenuItem

class Command(BaseCommand):
    help = "Load demo site structure"

    def create_menu(self):

        MenuItem.objects.all().delete()
        item = MenuItem.objects.create(
            parent = None,
            title = 'Home',
            url_name ='/',
            category = 'sidebar',  #sidebar, sidebarfooter,
            is_reversed = False,
            reversed_kwargs = None,
            reversed_args = None,
            is_widget = False,
            icon = 'fa fa-home',
            only_icon = False
        )
        blog = MenuItem.objects.create(
            parent = None,
            title = 'Blog',
            url_name ='/',
            category = 'sidebar',  #sidebar, sidebarfooter,
            is_reversed = False,
            reversed_kwargs = None,
            reversed_args = None,
            is_widget = False,
            icon = 'fa fa-edit',
            only_icon = False
        )
        blogentry = MenuItem.objects.create(
            parent = blog,
            title = 'Blog entries',
            url_name ='blog:entrylist',
            category = 'sidebar',  #sidebar, sidebarfooter,
            is_reversed = True,
            reversed_kwargs = None,
            reversed_args = None,
            is_widget = False,
            icon = 'fa fa-build',
            only_icon = False
        )
        blogentry = MenuItem.objects.create(
            parent = blog,
            title = 'Create  entry',
            url_name ='blog:entrycreate',
            category = 'sidebar',  #sidebar, sidebarfooter,
            is_reversed = True,
            reversed_kwargs = None,
            reversed_args = None,
            is_widget = False,
            icon = 'fa fa-build',
            only_icon = False
        )
        item = MenuItem.objects.create(
            parent = item,
            title = 'Dashboard',
            url_name ='#',
            category = 'sidebar',  #sidebar, sidebarfooter,
            is_reversed = False,
            reversed_kwargs = None,
            reversed_args = None,
            is_widget = False,
            icon = '',
            only_icon = False
        )

        extrawidget = MenuItem.objects.create(
            parent = None,
            title = 'Custom Widgets',
            url_name ='/',
            category = 'sidebar',  #sidebar, sidebarfooter,
            is_reversed = False,
            reversed_kwargs = None,
            reversed_args = None,
            is_widget = False,
            icon = 'fa fa-home',
            only_icon = False
        )
        cwidget = MenuItem.objects.create(
            parent=extrawidget,
            title='Form Widgets',
            url_name='#',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )
        MenuItem.objects.create(
            parent=cwidget,
            title='Knob Widgets',
            url_name='knobwidgets',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )
        MenuItem.objects.create(
            parent=cwidget,
            title='Color Widgets',
            url_name='colorwidgets',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )

        MenuItem.objects.create(
            parent=cwidget,
            title='Autocomplete Widgets',
            url_name='pgroup-list',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )
        noti=MenuItem.objects.create(
            parent = item,
            title = 'Create notification',
            url_name ='/create/notification',
            category = 'sidebar',  #sidebar, sidebarfooter,
            is_reversed = False,
            reversed_kwargs = None,
            reversed_args = None,
            is_widget = False,
            icon = 'fa fa-power-off',
            only_icon = False
        )
        MenuItem.objects.create(
            parent = item,
            title = 'Create notification email',
            url_name ='/create/notification?email=1',
            category = 'sidebar',  #sidebar, sidebarfooter,
            is_reversed = False,
            reversed_kwargs = None,
            reversed_args = None,
            is_widget = False,
            icon = 'fa fa-power-off',
            only_icon = False
        )

        MenuItem.objects.create(
            parent = item,
            title = 'People group',
            url_name ='pgroup-list',
            category = 'sidebar',  #sidebar, sidebarfooter,
            is_reversed = True,
            reversed_kwargs = None,
            reversed_args = None,
            is_widget = False,
            icon = 'fa fa-power-off',
            only_icon = False
        )
        MenuItem.objects.create(
            parent = item,
            title = 'People group create',
            url_name ='pgroup-add',
            category = 'sidebar',  #sidebar, sidebarfooter,
            is_reversed = True,
            reversed_kwargs = None,
            reversed_args = None,
            is_widget = False,
            icon = 'fa fa-power-off',
            only_icon = False
        )

        MenuItem.objects.create(
            parent = item,
            title = 'Country list',
            url_name ='demoapp_country_list',
            category = 'sidebar',  #sidebar, sidebarfooter,
            is_reversed = True,
            reversed_kwargs = None,
            reversed_args = None,
            is_widget = False,
            icon = 'fa fa-power-off',
            only_icon = False
        )
        MenuItem.objects.create(
            parent = item,
            title = 'Person list',
            url_name ='demoapp_person_list',
            category = 'sidebar',  #sidebar, sidebarfooter,
            is_reversed = True,
            reversed_kwargs = None,
            reversed_args = None,
            is_widget = False,
            icon = 'fa fa-power-off',
            only_icon = False
        )
        MenuItem.objects.create(
            parent = item,
            title = 'Dashboard widgets',
            url_name ='dashboard',
            category = 'sidebar',  #sidebar, sidebarfooter,
            is_reversed = True,
            reversed_kwargs = None,
            reversed_args = None,
            is_widget = False,
            icon = 'fa fa-power-off',
            only_icon = False
        )
        item = MenuItem.objects.create(
            parent = None,
            title = 'Logout',
            url_name ='/logout',
            category = 'sidebarfooter',  #sidebar, sidebarfooter,
            is_reversed = False,
            reversed_kwargs = None,
            reversed_args = None,
            is_widget = False,
            icon = 'fa fa-power-off',
            only_icon = True
        )


        item = MenuItem.objects.create(
            parent = None,
            title = '',
            url_name ='djgentelella.menu_widgets.palette.PalleteWidget',
            category = 'sidebarfooter',
            is_reversed = False,
            reversed_kwargs = None,
            reversed_args = reverse('help'),
            is_widget = True,
            icon = 'fa fa-envelope-o',
            only_icon = True
        )
        item = MenuItem.objects.create(
            parent = None,
            title = 'top_navigation',
            url_name ='djgentelella.notification.widgets.NotificationMenu',
            category = 'main',
            is_reversed = False,
            reversed_kwargs = None,
            reversed_args = reverse('notifications'),
            is_widget = True,
            icon = 'fa fa-envelope',
            only_icon = False
        )

    def create_countries(self):
        Country.objects.all().delete()
        data=[
            Country(name="Costa Rica"),
            Country(name="Panamá"),
            Country(name="Nicaragua"),
            Country(name="El Salvador"),
            Country(name="Guatemala"),
            Country(name="Hondura"),
            Country(name="Belize"),
        ]
        Country.objects.bulk_create(data)

    def create_person(self):
        for x in range(10):
            Person.objects.create(
                name = "Person "+str(x),
                num_children = randint(1, 10),
                country = Country.objects.all().order_by('?').first(),
                born_date = now(),
                last_time = now()
            )

    def handle(self, *args, **options):
        self.create_menu()
        self.create_countries()
        self.create_person()