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
            url_name ='/',
            category = 'sidebar',  #sidebar, sidebarfooter,
            is_reversed = False,
            reversed_kwargs = None,
            reversed_args = None,
            is_widget = False,
            icon = '',
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