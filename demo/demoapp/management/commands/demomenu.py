from django.contrib.sites.models import Site
from django.core.management import BaseCommand

from djgentelella.models import MenuItem
from djgentelella.utils import set_settings


class Command(BaseCommand):
    help = 'Load demo site structure'

    def add_arguments(self, parser):
        parser.add_argument(
            '--with-site', action='store_true',
            help='Also create a second Site with menu items and settings of '
                 'its own (docs/source/sites.rst).')
        parser.add_argument(
            '--site-domain', default='127.0.0.1',
            help='Domain of that second Site; browse the demo with this host '
                 'to see it. Default: 127.0.0.1 (localhost stays global).')

    def handle(self, *args, **options):
        self.create_global_menu()
        if options['with_site']:
            self.create_site_menu(options['site_domain'])

    def create_site_menu(self, domain):
        """A second Site: one item of its own, one override, one setting."""
        site, _created = Site.objects.get_or_create(
            domain=domain, defaults={'name': 'Demo site 2'})
        MenuItem.objects.filter(site=site).delete()
        MenuItem.objects.create(
            title='Site 2 home',
            url_name='home',
            category='main',
            is_reversed=True,
            icon='fa fa-building',
            position=2,
            site=site,
        )
        # Same url_name and category as the global "Icons": on this Site it
        # replaces that item, children included.
        icons = MenuItem.objects.create(
            title='Icons (site 2)',
            url_name='fontawesome_icons',
            category='main',
            is_reversed=True,
            icon='fa fa-star-o',
            position=1,
            site=site,
        )
        MenuItem.objects.create(
            parent=icons,
            title='Font Awesome',
            url_name='fontawesome_icons',
            category='main',
            is_reversed=True,
            icon='fa fa-flag-o',
            site=site,
        )
        set_settings('sidebar_title', 'Demo site 2', site=site)
        self.stdout.write('Site %s: menu and settings created' % site.domain)

    def create_global_menu(self):
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

        # One level deeper than anything else in the demo: the top menu draws
        # its nested levels itself (Bootstrap 5 has no submenus), so the depth
        # at which they stop working is the thing worth being able to see.
        MenuItem.objects.create(
            parent=base2_2_1_1,
            title='Base 2 de 2 de 1 de 1 de 1',
            url_name='/',
            category='main',
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )

        MenuItem.objects.create(
            parent=base2_2_1_1,
            title='Base 2 de 2 de 1 de 1 de 2',
            url_name='/',
            category='main',
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

        # The theme roller and the feedback inbox (W32): the look of each Site
        # and what the users send with the feedback button.
        look = MenuItem.objects.create(
            parent=None,
            title='Theme and feedback',
            url_name='gt_theme_roller',
            category='main',
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-paint-brush',
            only_icon=False,
            position=2
        )
        for position, (title, url_name, icon) in enumerate([
            ('Theme', 'gt_theme_roller', 'fa fa-paint-brush'),
            ('Feedback', 'gt_feedback_inbox', 'fa fa-comments'),
        ]):
            MenuItem.objects.create(
                parent=look,
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

        # Metadata translations (W34): the translation screens, and the
        # language switcher of the top bar. The titles are written in
        # English; the Spanish translation is what the demo shows by default.
        MenuItem.objects.create(
            parent=look,
            title='Translations',
            translations={'es': 'Traducciones'},
            url_name='gt_translations',
            category='main',
            is_reversed=True,
            is_widget=False,
            icon='fa fa-language',
            only_icon=False,
            position=2,
        )
        MenuItem.objects.create(
            parent=None,
            title='Language',
            url_name='demoapp.menu_widgets.LanguageMenu',
            category='main',
            is_reversed=False,
            is_widget=True,
            only_icon=False,
            position=3,
        )
