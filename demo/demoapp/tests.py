from datetime import date, timedelta, datetime
from django import forms
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.forms import forms
from django.forms import formset_factory
from django.template import Template, Context
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.urls import reverse_lazy, path
from rest_framework import serializers
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

from demoapp.calendar.forms import CalendarForm, CalendarModelform
from demoapp.models import Event, Calendar
from djgentelella.views.storyline import StorylineBuilder
from djgentelella.views.storymap import BaseStoryMapMBView, BaseStoryMapGPView
from djgentelella.widgets.calendar import CalendarInput
from djgentelella.widgets.storyline import UrlStoryLineInput
from djgentelella.widgets.storymap import MapBasedStoryMapInput, GigaPixelStoryMapInput


# Create your tests here.


class CalendarWidgetTest(TestCase):

    def setUp(self):
        self.events = [
            {
                'title': 'Event 1',
                'start': datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S.%f"),
                'end': datetime.strftime(datetime.now() + timedelta(minutes=30), "%Y-%m-%d %H:%M:%S.%f")
            },
            {
                'title': 'Event 2',
                'start': datetime.strftime(datetime.now() + timedelta(days=1), "%Y-%m-%d %H:%M:%S.%f"),
                'end': datetime.strftime(datetime.now() + timedelta(days=1, minutes=30), "%Y-%m-%d %H:%M:%S.%f")
            },
            {
                'title': 'Event 3',
                'start': datetime.strftime(datetime.now() + timedelta(days=2), "%Y-%m-%d %H:%M:%S.%f"),
                'end': datetime.strftime(datetime.now() + timedelta(days=2, minutes=30), "%Y-%m-%d %H:%M:%S.%f")
            },
        ]

        self.calendarWidget = forms.CharField(
            widget=CalendarInput(
                calendar_attrs={
                    'initialView': 'timeGridWeek',
                },
                events=self.events
            )
        )

    def test_widget_events(self):
        self.assertEquals(self.calendarWidget.widget.events, self.events)

    def test_calendar_attrs(self):
        self.assertDictEqual(self.calendarWidget.widget.calendar_attrs, {'initialView': 'timeGridWeek'})

    def test_wrong_field_names(self):
        wrong_fields_event = [
            {
                'name': 'Event 4',
                'startDate': datetime.now(),
                'endDate': datetime.now() + timedelta(days=1)
            }
        ]
        calendar = forms.CharField(
            widget=CalendarInput(
                calendar_attrs={},
                events=wrong_fields_event
            )
        )
        with self.assertRaisesMessage(serializers.ValidationError, "Serializer data is not accepted."):
            calendar.widget.events_to_json(calendar.widget.events)

    def test_past_end_date(self):
        wrong_date_event = [
            {
                'title': 'Event 4',
                'start': datetime.now() + timedelta(days=1),
                'end': datetime.now()
            }
        ]
        calendar = forms.CharField(
            widget=CalendarInput(
                calendar_attrs={},
                events=wrong_date_event
            )
        )
        with self.assertRaisesMessage(serializers.ValidationError, "Event end date must occur after start date"):
            calendar.widget.events_to_json(calendar.widget.events)

    def test_empty_events(self):
        empty_event = {}
        calendar = forms.CharField(
            widget=CalendarInput(
                calendar_attrs={},
                events=empty_event
            )
        )
        with self.assertRaisesMessage(serializers.ValidationError, "Empty event parameter."):
            calendar.widget.events_to_json(calendar.widget.events)

    def test_JSONField_events(self):
        calendar = Calendar.objects.create(
            title='CalendarTest',
            events={
                'events': self.events,
            }
        )
        calendarWidget = forms.CharField(
            widget=CalendarInput(
                calendar_attrs={},
                events=calendar.events['events']
            )
        )
        self.assertEquals(calendarWidget.widget.events, self.events)

class FormCalendarWidgetTest(TestCase):

    def setUp(self):
        self.calendar = Calendar.objects.create(title='Calendar 1', options={})
        self.event = Event.objects.create(
            calendar=self.calendar,
            title='Event 1',
            start=date.today(),
            end=date.today() + timedelta(minutes=30)
        )
        self.factory = RequestFactory()
        self.form = CalendarForm()
        self.modelForm = CalendarModelform()

    def render(self, msg, context={}):
        template = Template(msg)
        context = Context(context)
        return template.render(context)

    def test_widget_id_form(self):
        calendar_id = self.render('{{form.calendar.id_for_label}}', {'form': self.form})
        self.assertEquals(calendar_id, 'id_calendar')

    def test_events_src_input(self):
        calendar_name = self.render('{{form.calendar.html_name}}', {'form': self.form})
        self.assertEquals(calendar_name, 'calendar')

    def test_widget_name_form(self):
        calendar_input = self.render('{{form}}', {'form': self.form})
        self.assertIn('name="calendar_display"', calendar_input)

    def test_widget_not_required(self):
        self.form.fields['calendar'].required = True
        calendar_required = self.render('{{form.calendar.required}}', {'form': self.form})
        self.assertFalse(calendar_required)

    def test_widget_from_modelform(self):
        events = self.render('{{form.events}}', {'form': self.modelForm})
        self.assertIn('name="events_display"', events)

    def test_widget_formset(self):
        CalendarFormSet = formset_factory(CalendarForm, extra=2)
        formset = CalendarFormSet()
        for formIndex in range(len(formset)):
            calendar_name = self.render('{{form}}', {'form': formset[formIndex]})
            self.assertIn(f'name="form-{formIndex}-calendar_display"', calendar_name)


class CalendarWidgetFormSeleniumTest(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.selenium = WebDriver()
        cls.selenium.implicitly_wait(10)

    def setUp(self):
        self.calendar = Calendar.objects.create(title='Calendar 1', options={})
        self.events = [
            Event(calendar=self.calendar, title='Event 1', start=date.today(),
                  end=date.today() + timedelta(minutes=30)),
            Event(calendar=self.calendar, title='Event 2', start=date.today() + timedelta(days=1),
                  end=date.today() + timedelta(minutes=30)),
            Event(calendar=self.calendar, title='Event 3', start=date.today() + timedelta(days=2),
                  end=date.today() + timedelta(minutes=30))
        ]
        Event.objects.bulk_create(self.events)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()

    def test_events_showing(self):
        self.selenium.get(self.live_server_url + '/calendar_view')
        assert 'Event 1' in self.selenium.page_source
        assert 'Event 2' in self.selenium.page_source
        assert 'Event 3' in self.selenium.page_source

    def test_events_save(self):
        self.selenium.get(self.live_server_url + '/calendar_view')
        self.selenium.find_element(By.ID, 'id_title').send_keys('CalendarTest')
        self.selenium.find_element(By.XPATH, '//button[type="submit"]').click()
        assert self.events == Calendar.objects.last().events


class StoryMapWithSeleniumTestCase(StaticLiveServerTestCase):

    @classmethod
    def setUpClass(cls):
        cls.selenium = WebDriver()
        cls.selenium.implicitly_wait(10)
        super(StoryMapWithSeleniumTestCase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(StoryMapWithSeleniumTestCase, cls).tearDownClass()
        cls.selenium.quit()

    def test_display_storymaps(self):
        self.selenium.get(self.live_server_url)
        # Find storymap obj
        assert 'mapbased_storymap' in self.selenium.page_source
        assert 'gigapixel_storymap' in self.selenium.page_source

    def test_slides_title_data(self):
        self.selenium.get(self.live_server_url)

        response = self.selenium.find_element(By.CSS_SELECTOR, 'body').text
        self.assertTrue('COSTA RICA PLACES TO VISIT' in response)
        self.assertTrue('A Sunday on La Grande Jatte' in response)


class StoryMapFormWidgetTest(TestCase):

    def setUp(self):
        class StoryMapFormClass(forms.Form):
            gp_storymap = forms.CharField(widget=GigaPixelStoryMapInput, required=False)
            mb_storymap = forms.CharField(widget=MapBasedStoryMapInput, disabled=True)

        self.form = StoryMapFormClass()

    def render(self, msg, context={}):
        template = Template(msg)
        context = Context(context)
        return template.render(context)

    def test_widget_id_form(self):
        gp_storymap_id = self.render('{{form.gp_storymap.id_for_label}}', {'form': self.form})
        mb_storymap_id = self.render('{{form.mb_storymap.id_for_label}}', {'form': self.form})
        self.assertEqual(gp_storymap_id, 'id_gp_storymap')
        self.assertEqual(mb_storymap_id, 'id_mb_storymap')

    def test_widget_name_form(self):
        gp_storymap_name = self.render('{{form.gp_storymap.html_name}}', {'form': self.form})
        mb_storymap_name = self.render('{{form.mb_storymap.html_name}}', {'form': self.form})
        self.assertEqual(gp_storymap_name, 'gp_storymap')
        self.assertEqual(mb_storymap_name, 'mb_storymap')

    def test_form_field_id(self):
        storymap = self.render('{{form}}', {'form': self.form})
        self.assertIn('id="id_gp_storymap"', storymap)
        self.assertIn('id="id_mb_storymap"', storymap)

    def test_form_field_data_widget(self):
        storymap = self.render('{{form}}', {'form': self.form})
        self.assertIn('data-widget="GigaPixelStoryMapInput"', storymap)
        self.assertIn('data-widget="MapBasedStoryMapInput"', storymap)

    def test_widget_required_false(self):
        required = self.render('{{form.gp_storymap.required}}', {'form': self.form})
        self.assertFalse(required)

    def test_widget_disabled_true(self):
        disabled = self.render('{{form.mb_storymap.disabled}}', {'form': self.form})
        self.assertFalse(disabled)


class MapBasedStoryMapWidgetTestCase(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.mapbased_view = BaseStoryMapMBView()
        self.storymap = forms.CharField(widget=MapBasedStoryMapInput(
            attrs={"data-url": reverse_lazy('examplestorymapmb-list')}))

        self.url = reverse('examplestorymapmb-list')

    def test_assert_response_valid_data(self):
        request = self.factory.get(self.url)
        response = self.mapbased_view.list(request)

        self.assertEqual(response.status_code, 200)

    def test_assert_response_invalid_data(self):
        request = self.factory.get(self.url)

        response = self.mapbased_view.list(request)


class GigaPixelStoryMapWidgetTestCase(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.gigapixel_view = BaseStoryMapGPView()

        self.url = reverse('examplestorymapgp-list')

    def get_storymap_options(self):
        return {
            "map_type": "zoomify",
            "map_background_color": "#333",
            "map_as_image": True,
            "calculate_zoom": False,
            "zoomify": {
                "path": "http://cdn.verite.co/maps/zoomify/seurat/",
                "width": 30000,
                "height": 19970,
                "tolerance": 0.9,
                "attribution": "<a href='http://www.google.com/culturalinstitute/asset-viewer/a-sunday-on-la-grande-jatte-1884/twGyqq52R-lYpA?projectId=art-project' target='_blank'>Google Art Project</a>"
            }
        }

    def test_assert_response_valid_data(self):
        request = self.factory.get(self.url)
        response = self.gigapixel_view.list(request)

        self.assertEqual(response.status_code, 200)

    def test_assert_response_invalid_data(self):
        request = self.factory.get(self.url)

        def get_font():
            return 'stock:opensans-gentiumbook'

        def get_storymap_body():
            return {
                "map_type": "zoomify",
                "slides": [
                    {
                        "date": "",
                        "location": {
                            "icon": "http://maps.gstatic.com/intl/en_us/mapfiles/ms/micons/blue-pushpin.png",
                            "line": True
                        },
                        "background": {
                            "url": "http://gigapixel.knightlab.com/seurat/seurat_portrait.jpg",
                            "color": "#000",
                            "opacity": 50
                        },
                        "text": {
                            "headline": "A Sunday on La Grande Jatte <br><small>Georges Seurat</small>",
                            "text": "In his best-known and largest painting, Georges Seurat depicted people relaxing in a suburban park on an island in the Seine River called La Grande Jatte."
                        },
                        "type": "overview"
                    },
                    {
                        "date": "",
                        "location": {
                            "icon": "http://maps.gstatic.com/intl/en_us/mapfiles/ms/micons/blue-pushpin.png",
                            "lat": 75.71563324165896,
                            "line": True,
                            "lon": -132.1875,
                            "zoom": 6
                        },
                        "text": {
                            "headline": "Small Horizontal Brushstrokes",
                            "text": "Work began in 1884. The artist worked on the painting in several campaigns, beginning in 1884 with a layer of small horizontal brushstrokes of complementary colors."
                        }
                    }
                ],
                "zoomify": {
                    "attribution": "",
                    "height": 19970,
                    "path": "http://gigapixel.knightlab.com/seurat/",
                    "tolerance": 0.9,
                    "width": 30000
                }
            }

        self.gigapixel_view.get_font_css = get_font
        self.gigapixel_view.get_storymap = get_storymap_body

        response = self.gigapixel_view.list('')
        self.assertEqual(response.status_code, 200)

class StorylineWidgetSeleniumTest(StaticLiveServerTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.selenium = webdriver.Chrome(executable_path='/home/ricardoalfaro/Descargas/chromedriver')
        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def test_widget_assignation(self):
        # Choose your url to visit
        self.selenium.get(self.live_server_url)
        assert 'id_storyline' in self.selenium.page_source

    def test_widget_in_page(self):
        self.selenium.get(self.live_server_url)
        storyline = self.selenium.find_element_by_class_name('storyline-wrapper')
        # deprecated, change to find element(by='class_name', value= "")

        self.assertNotEqual(storyline, None)
        self.assertEqual("/gtapis/storyline/", storyline.get_attribute('data-url'))
        self.assertEqual("storyline-wrapper", storyline.get_attribute('class'))
        self.assertEqual("568", storyline.get_attribute('height'))
        self.assertEqual("1112", storyline.get_attribute('width'))
        self.assertEqual("UrlStoryLineInput", storyline.get_attribute('data-widget'))


class StorylineWidgetUnitTest(TestCase):

    def setUp(self):

        self.factory = RequestFactory()

        self.data = {
            "datetime_column_name": "date",
            "datetime_format": "%Y-%m-%d",
            "data_column_name": "income"}

        self.invalid_data_1 = {
            "datetime_format": "%Y-%m-%d",
            "data_column_name": "income"
        }
        self.invalid_data_2 = {
            "datetime_column_name": "date",
            "datetime_format": "%Y-%m-%d"
        }
        self.invalid_data_3 = {
            "datetime_column_name": "date",
            "data_column_name": "income"
        }

        self.chart = {
            "datetime_format": "%Y",
            "y_axis_label": "Income"
        }
        self.invalid_chart = {
            "y_axis_label": "Income"
        }

        self.slider = {
            "start_at_card": "1",
            "title_column_name": "title",
            "text_column_name": "text",
        }
        self.invalid_slider_1 = {
            "start_at_card": "1",
            "text_column_name": "text",
        }
        self.invalid_slider_2 = {
            "start_at_card": "1",
            "title_column_name": "title",
        }

        self.options = {
            "data": self.data,
            "chart": self.chart,
            "slider": self.slider
        }

        csv = ['date,income,title,text,,',
               '1984-01-01,48720,,,,\r\n',
               '1985-01-01,49631,,\r\n', # two less columns in this line, this is valid, should be handled by view
               '1986-01-01,51388,,,,\r\n',
               '1987-01-01,52032,,,,\r\n',
               '1988-01-01,52432,,,,\r\n',
               '1989-01-01,53367,Reagan Boom Boom,"Two major underlying factors lead to a weakening U.S. economy—restrictive moves from the Federal Reserve designed to curb inflation, and a depreciating real estate market.",,\r\n',
               '1990-01-01,52684,Hello Downturn My Old Friend,"It’s all over in July, the last month of this period’s economic expansion. When Iraq invades Kuwait in August, oil prices skyrocket, and consumer confidence tanks. We head into a recession.",,\r\n',
               '1991-01-01,51145,,,,\r\n',
               '1992-01-01,50725,,,,\r\n',
               '1993-01-01,50478,Internet FTW,"Okay, technically the internet isn’t acting alone. Alongside this technology boon, the housing market starts to recover, due in part to lower interest rates and energy prices. People start making and spending money again.",,\r\n',
               '1994-01-01,51065,,,,\r\n',
               '1995-01-01,52664,,,,\r\n',
               '1996-01-01,53407,,,,\r\n',
               '1997-01-01,54506,,,,\r\n',
               '1998-01-01,56510,,,,view\r\n',
               '1999-01-01,57909,"Internet, You Have Failed Me","What’s the sound of countless investors sneaking away from Silicon Valley? A dot-com bubble burst. Investors see no path to revenue, dot-coms shut their doors, and the economy slumps. Goodbye, pets.com.",,\r\n',
               '2000-01-01,57790,,,,\r\n',
               '2001-01-01,56531,,,,\r\n']

        invalid_csv = ['date,income,title,text,,',
                       '1984-01-01,48720,,,,\r\n',
                       '1985-01-01,49631,,,,\r\n',
                       '1986-01-01,51388,,,,,\r\n', # one more column in this line, this is incalid
                       '1987-01-01,52032,,,,\r\n',
                       '1988-01-01,52432,,,,\r\n',
                       '1989-01-01,53367,Reagan Boom Boom,"Two major underlying factors lead to a weakening U.S. economy—restrictive moves from the Federal Reserve designed to curb inflation, and a depreciating real estate market.",,\r\n',
                       '1990-01-01,52684,Hello Downturn My Old Friend,"It’s all over in July, the last month of this period’s economic expansion. When Iraq invades Kuwait in August, oil prices skyrocket, and consumer confidence tanks. We head into a recession.",,\r\n',
                       '1991-01-01,51145,,,,']

        self.attrs = {
            "data-url": reverse_lazy('examplestoyline-list'),
            "height": 568,
            "width": 1112,
            "data-url_name": "examplestoyline"}

        # self.storylineWidget = forms.Charfield(widget=UrlStoryLineInput(attrs=self.attrs))

    def test_OptionsSerializer_data(self):
        from djgentelella.views.storyline import OptionsSerializer

        bad_data = {'data': self.invalid_data_1,'chart': self.chart,'slider': self.slider}
        new_serializer = OptionsSerializer(data=bad_data)
        self.assertEqual(new_serializer.is_valid(), False)
        self.assertEqual(new_serializer.errors['data']['datetime_column_name'][0], "Este campo es requerido.")

        bad_data = {'data': self.invalid_data_2, 'chart': self.chart,'slider': self.slider}
        new_serializer = OptionsSerializer(data=bad_data)
        self.assertEqual(new_serializer.is_valid(), False)
        self.assertEqual(new_serializer.errors['data']['data_column_name'][0], "Este campo es requerido.")

        bad_data = {'data': self.invalid_data_3,'chart': self.chart,'slider': self.slider}
        new_serializer = OptionsSerializer(data=bad_data)
        self.assertEqual(new_serializer.is_valid(), False)
        self.assertEqual(new_serializer.errors['data']['datetime_format'][0], "Este campo es requerido.")

    def test_OptionsSerializer_chart(self):
        from djgentelella.views.storyline import OptionsSerializer

        bad_data = {'data': self.data, 'chart': self.invalid_chart, 'slider': self.slider}
        new_serializer = OptionsSerializer(data=bad_data)
        self.assertEqual(new_serializer.is_valid(), False)
        self.assertEqual(new_serializer.errors['chart']['datetime_format'][0], "Este campo es requerido.")

    def test_OptionsSerializer_slider(self):
        from djgentelella.views.storyline import OptionsSerializer

        bad_data = {'data': self.data,'chart': self.chart,'slider': self.invalid_slider_1}
        new_serializer = OptionsSerializer(data=bad_data)
        self.assertEqual(new_serializer.is_valid(), False)
        self.assertEqual(new_serializer.errors['slider']['title_column_name'][0], "Este campo es requerido.")

        bad_data = {'data': self.data,'chart': self.chart,'slider': self.invalid_slider_2}
        new_serializer = OptionsSerializer(data=bad_data)
        self.assertEqual(new_serializer.is_valid(), False)
        self.assertEqual(new_serializer.errors['slider']['text_column_name'][0], "Este campo es requerido.")

    def test_OptionsSerializer_valid(self):
        from djgentelella.views.storyline import OptionsSerializer

        data = {'data': self.data,'chart': self.chart,'slider': self.slider}
        new_serializer = OptionsSerializer(data=data)
        self.assertEqual(new_serializer.is_valid(), True)

    from djgentelella.urls import urlpatterns as base_patterns
    from django.test.utils import override_settings

    user_list = StorylineBuilder.as_view({'get': 'list'})
    user_detail = StorylineBuilder.as_view({'get': 'retrieve'})

    urlpatterns = base_patterns + [
        path('storylinecsv', user_detail, name="test_get_csv-detail"),
        path('storylinecsv', user_list, name="test_get_csv-list"),
    ]

    @override_settings(ROOT_URLCONF=__name__)
    def test_list_view(self):
        self.reload_urlconf()
        # importar la vista
        # mockear el request
        # view = StoryBuilder
        # view.create_options() = self.options ### ver como sobreescribirlo o asignarlo
        # response = view.list(self, request)  ### ver como llamarla y como mockear el request
        # response != 200 cuando no son parametros validos
        # lo mismo con retrieve
        from djgentelella.views.storyline import StorylineBuilder

        def options():
            return self.options

        list_view = StorylineBuilder()
        list_view.create_options = options

        request = self.factory.get('')
        request.GET = {'url_name': 'examplestoryline'} #example of working retrieve view, to prove list view functionality

        breakpoint()
        response = list_view.list(request)
        self.assertEqual(response.status_code, 200)

    def test_widget_form(self):
        from django import forms

        class FormClass(forms.Form):
            storyline = forms.CharField(widget=UrlStoryLineInput, disabled=True)

        form = FormClass()
        idfield = self.render("{{form.storyline.id_for_label}}", {'form': form})
        idname = self.render("{{form.storyline.html_name}}", {'form': form})
        fieldstr = self.render("{{form.storyline}}", {'form': form})

        self.assertEqual(idfield, "id_storyline")
        self.assertEqual(idname, "storyline")
        self.assertIn('id="id_storyline"', fieldstr)
        self.assertIn('data-widget="UrlStoryLineInput"', fieldstr)
        self.assertIn('name="storyline"', fieldstr)


