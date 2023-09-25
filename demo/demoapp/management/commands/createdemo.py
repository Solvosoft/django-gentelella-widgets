from random import randint

from django.core.management import BaseCommand
from django.urls import reverse
from django.utils.timezone import now

from demoapp import models
from djgentelella.models import MenuItem


class Command(BaseCommand):
    help = "Load demo site structure"

    def create_menu(self):

        MenuItem.objects.all().delete()
        item = MenuItem.objects.create(
            parent=None,
            title='Home',
            url_name='/',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )
        blog = MenuItem.objects.create(
            parent=None,
            title='Blog',
            url_name='/',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-edit',
            only_icon=False
        )
        blogentry = MenuItem.objects.create(
            parent=blog,
            title='Blog entries',
            url_name='blog:entrylist',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-build',
            only_icon=False
        )
        blogentry = MenuItem.objects.create(
            parent=blog,
            title='Create  entry',
            url_name='blog:entrycreate',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-build',
            only_icon=False
        )
        dashboard = MenuItem.objects.create(
            parent=item,
            title='Dashboard',
            url_name='#',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='',
            only_icon=False
        )
        item = MenuItem.objects.create(
            parent=item,
            title='Crud / notifications',
            url_name='#',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='',
            only_icon=False
        )

        extrawidget = MenuItem.objects.create(
            parent=None,
            title='Custom Widgets',
            url_name='/',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )
        cwidget = MenuItem.objects.create(
            parent=extrawidget,
            title='User Media widget',
            url_name='mediaupload_view',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-camera',
            only_icon=False
        )

        cwidget = MenuItem.objects.create(
            parent=extrawidget,
            title='Formset Widgets',
            url_name='#',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-cab',
            only_icon=False
        )
        c1widget = MenuItem.objects.create(
            parent=cwidget,
            title='Formset add',
            url_name='add_formset',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-subway',
            only_icon=False
        )
        c2widget = MenuItem.objects.create(
            parent=cwidget,
            title='Model Formset',
            url_name='add_model_formset',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-plane',
            only_icon=False
        )
        cwidget = MenuItem.objects.create(
            parent=extrawidget,
            title='Datatables',
            url_name='datatable_view',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-table',
            only_icon=False
        )
        cwidget = MenuItem.objects.create(
            parent=extrawidget,
            title='Object Management',
            url_name='person_object_management',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-microchip',
            only_icon=False
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
        readonlywidget = MenuItem.objects.create(
            parent=extrawidget,
            title='ReadOnly Widgets',
            url_name='#',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-list-alt',
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
            icon='fa fa-eyedropper',
            only_icon=False
        )
        inputmask = MenuItem.objects.create(
            parent=cwidget,
            title='Input Mask',
            url_name='input-mask-list',
            category='sidebar',
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-cutlery',
            only_icon=False
        )
        daterange = MenuItem.objects.create(
            parent=cwidget,
            title='Date Range',
            url_name='date-range-list',
            category='sidebar',
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-balance-scale',
            only_icon=False
        )
        tagging = MenuItem.objects.create(
            parent=cwidget,
            title='Tagging',
            url_name='input_tagging-list',
            category='sidebar',
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-superpowers',
            only_icon=False
        )
        Tinymce = MenuItem.objects.create(
            parent=cwidget,
            title='Tinymce Editor',
            url_name='tinymce-list',
            category='sidebar',
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-sticky-note',
            only_icon=False
        )

        Calendar = MenuItem.objects.create(
            parent=readonlywidget,
            title='Calendar',
            url_name='calendar_view',
            category='sidebar',
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-calendar',
            only_icon=False
        )

        Gigapixel = MenuItem.objects.create(
            parent=readonlywidget,
            title='Gigapixel StoryMap',
            url_name='gigapixel_view',
            category='sidebar',
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-map-marker',
            only_icon=False
        )

        Mapbased = MenuItem.objects.create(
            parent=readonlywidget,
            title='Mapbased StoryMap',
            url_name='mapbased_view',
            category='sidebar',
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-map',
            only_icon=False
        )

        StoryLine = MenuItem.objects.create(
            parent=readonlywidget,
            title='StoryLine',
            url_name='storyline_view',
            category='sidebar',
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-vine',
            only_icon=False
        )
        TimeLine = MenuItem.objects.create(
            parent=readonlywidget,
            title='Timeline',
            url_name='timeline_view',
            category='sidebar',
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-clock-o',
            only_icon=False
        )

        chart = MenuItem.objects.create(
            parent=dashboard,
            title='Charts',
            url_name='chartjs_view',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-line-chart',
            only_icon=False
        )
        noti = MenuItem.objects.create(
            parent=item,
            title='Create notification',
            url_name='/create/notification',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-power-off',
            only_icon=False)

        daterange = MenuItem.objects.create(
            parent=cwidget,
            title='Grid Slider',
            url_name='grid-slider-list',
            category='sidebar',
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )

        chunckedupload = MenuItem.objects.create(
            parent=cwidget,
            title='Chuncked Upload',
            url_name='chunkeduploaditem-list',
            category='sidebar',
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-download',
            only_icon=False
        )

        chunckedupload = MenuItem.objects.create(
            parent=cwidget,
            title='Select in modal',
            url_name='bt_modal_display',
            category='sidebar',
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-mouse-pointer',
            only_icon=False
        )

        chunckedupload = MenuItem.objects.create(
            parent=cwidget,
            title='Select2box',
            url_name='select2box-list',
            category='sidebar',
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-mouse-pointer',
            only_icon=False
        )

        noti = MenuItem.objects.create(
            parent=item,
            title='Create notification',
            url_name='/create/notification',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-power-off',
            only_icon=False
        )

        MenuItem.objects.create(
            parent=item,
            title='Create notification email',
            url_name='/create/notification?email=1',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-power-off',
            only_icon=False
        )

        MenuItem.objects.create(
            parent=item,
            title='Country list',
            url_name='demoapp_country_list',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-power-off',
            only_icon=False
        )
        MenuItem.objects.create(
            parent=item,
            title='Person list',
            url_name='demoapp_person_list',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-power-off',
            only_icon=False
        )
        MenuItem.objects.create(
            parent=dashboard,
            title='Element widgets',
            url_name='dashboard',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-table',
            only_icon=False
        )
        item = MenuItem.objects.create(
            parent=None,
            title='Logout',
            url_name='/accounts/logout/',  # DO manual
            category='sidebarfooter',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-power-off',
            only_icon=True
        )

        item = MenuItem.objects.create(
            parent=None,
            title='',
            url_name='djgentelella.menu_widgets.palette.PalleteWidget',
            category='sidebarfooter',
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=reverse('help'),
            is_widget=True,
            icon='fa fa-envelope-o',
            only_icon=True
        )
        item = MenuItem.objects.create(
            parent=None,
            title='top_navigation',
            url_name='djgentelella.notification.widgets.NotificationMenu',
            category='main',
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=reverse('notifications'),
            is_widget=True,
            icon='fa fa-envelope',
            only_icon=False
        )

    def create_autocomplete_menu(self):
        item = MenuItem.objects.create(
            parent=None,
            title='Remote autocomplete Widgets',
            url_name='/',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=False,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-home',
            only_icon=False
        )
        MenuItem.objects.create(
            parent=item,
            title='People group (Autocomplete)',
            url_name='pgroup-list',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-power-off',
            only_icon=False
        )
        MenuItem.objects.create(
            parent=item,
            title='Autocomplete related',
            url_name='abcde-list',
            category='sidebar',  # sidebar, sidebarfooter,
            is_reversed=True,
            reversed_kwargs=None,
            reversed_args=None,
            is_widget=False,
            icon='fa fa-power-off',
            only_icon=False
        )

    def create_countries(self):
        models.Country.objects.all().delete()
        data = [
            models.Country(name="Costa Rica"),
            models.Country(name="Panamá"),
            models.Country(name="Nicaragua"),
            models.Country(name="El Salvador"),
            models.Country(name="Guatemala"),
            models.Country(name="Hondura"),
            models.Country(name="Belize"),
        ]
        models.Country.objects.bulk_create(data)

    def create_person(self):
        models.Person.objects.all().delete()
        for x in range(10):
            models.Person.objects.create(
                name="Person " + str(x),
                num_children=randint(1, 10),
                country=models.Country.objects.all().order_by('?').first(),
                born_date=now(),
                last_time=now()
            )

    def create_comunities(self):
        models.Comunity.objects.all().delete()
        for x in range(10):
            models.Comunity.objects.create(name="Comunity " + str(x))

    def abcde(self):
        models.A.objects.all().delete()
        al, bl, cl, dl, el = [], [], [], [], []
        bid = cid = did = eid = 0

        for a in range(1, 11):
            al.append(models.A(display="A " + str(a), id=a))
            for b in range(1, 11):
                bid += 1
                bl.append(models.B(display="B %d a(%d)" %
                                           (b, a), id=bid, a_id=a))
                for c in range(1, 6):
                    cid += 1
                    cl.append(models.C(display="C %d b(%d) a(%d)" %
                                               (c, b, a), id=cid, b_id=bid))
                    for d in range(1, 5):
                        did += 1
                        dl.append(models.D(display="D %d c(%d) b(%d) a(%d)" % (
                            d, c, b, a), id=did, c_id=cid))
                        for e in range(1, 4):
                            eid += 1
                            el.append(
                                models.E(display="E %d d(%d) c(%d) b(%d) a(%d)" % (
                                    e, d, c, b, a), id=eid, d_id=did))
        models.A.objects.bulk_create(al)
        models.B.objects.bulk_create(bl)
        models.C.objects.bulk_create(cl)
        models.D.objects.bulk_create(dl)
        models.E.objects.bulk_create(el)

    def handle(self, *args, **options):
        self.create_menu()
        self.create_autocomplete_menu()
        self.create_countries()
        self.create_person()
        self.create_comunities()
        self.abcde()
