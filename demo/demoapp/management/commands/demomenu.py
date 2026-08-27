from django.core.management import BaseCommand

from djgentelella.models import MenuItem


class Command(BaseCommand):
    help = 'Load demo site structure'

    def handle(self, *args, **options):
        MenuItem.objects.filter(title__startswith='Base').delete()
        MenuItem.objects.filter(title='Icons').delete()

        base1 = MenuItem.objects.create(
            parent=None,
            title='Base 1',
            url_name='/',
            category='main',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )
        base2 = MenuItem.objects.create(
            parent=None,
            title='Base 2',
            url_name='/',
            category='main',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )
        base3 = MenuItem.objects.create(
            parent=None,
            title='Base 3',
            url_name='/',
            category='main',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )

        base2_1 = MenuItem.objects.create(
            parent=base2,
            title='Base 2 de 1',
            url_name='/',
            category='main',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )
        base2_2 = MenuItem.objects.create(
            parent=base2,
            title='Base 2 de 2',
            url_name='/',
            category='main',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )
        base2_3 = MenuItem.objects.create(
            parent=base2,
            title='Base 2 de 3',
            url_name='/',
            category='main',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )

        base2_2_1 = MenuItem.objects.create(
            parent=base2_2,
            title='Base 2 de 2 de 1',
            url_name='/',
            category='main',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )
        base2_2_2 = MenuItem.objects.create(
            parent=base2_2,
            title='Base 2 de 2 de 2',
            url_name='/',
            category='main',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )

        base2_2_1_1 = MenuItem.objects.create(
            parent=base2_2_1,
            title='Base 2 de 2 de 1 de 1',
            url_name='/',
            category='main',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )

        base2_2_1_2 = MenuItem.objects.create(
            parent=base2_2_1,
            title='Base 2 de 2 de 1 de 2',
            url_name='/',
            category='main',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )

        base2_2_1_3 = MenuItem.objects.create(
            parent=base2_2_1,
            title='Base 2 de 2 de 1 de 3',
            url_name='/',
            category='main',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )

        base2_2_2_1 = MenuItem.objects.create(
            parent=base2_2_2,
            title='Base 2 de 2 de 2 de 1',
            url_name='/',
            category='main',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )

        # Icon reference pages. is_reversed=True so the sidebar resolves the
        # url_name rather than carrying a hardcoded path, and each entry wears
        # an icon from the set it links to.
        icons = MenuItem.objects.create(
            parent=None,
            title='Icons',
            url_name='fontawesome_icons',
            category='main',
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-star',
            only_icon=False,
            position=1
        )
        for position, (title, url_name, icon) in enumerate([
            ('Font Awesome', 'fontawesome_icons', 'fa fa-flag-o'),
            ('Friconix', 'friconix_icons', 'fa fa-diamond'),
            ('Material Design', 'mdi_icons', 'fa fa-square-o'),
            ('Country flags', 'flag_icons', 'fa fa-globe'),
        ]):
            MenuItem.objects.create(
                parent=icons,
                title=title,
                url_name=url_name,
                category='main',
                is_reversed=True,
                reversed_kwargs=None,
                reversed_args=None,
                is_widget=False,
                icon=icon,
                only_icon=False,
                position=position
            )
