from django.core.management import BaseCommand

from djgentelella.models import MenuItem


class Command(BaseCommand):
    help = "Load demo site structure"

    def handle(self, *args, **options):
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
