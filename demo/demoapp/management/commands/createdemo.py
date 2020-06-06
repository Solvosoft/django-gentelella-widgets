from django.core.management import BaseCommand
from django.urls import reverse

from djgentelella.models import MenuItem

class Command(BaseCommand):
    help = "Load demo site structure"

    def handle(self, *args, **options):
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
            reversed_args = None,
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