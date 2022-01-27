from django.test import TestCase
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse_lazy
from selenium import webdriver
# Create your tests here.
from django import forms
from djgentelella.widgets.storyline import UrlStoryLineInput


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
        self.assertNotEqual(storyline, None)
        self.assertEqual("/gtapis/storyline/", storyline.get_attribute('data-url'))
        self.assertEqual("storyline-wrapper", storyline.get_attribute('class'))
        self.assertEqual("568", storyline.get_attribute('height'))
        self.assertEqual("1112", storyline.get_attribute('width'))
        self.assertEqual("UrlStoryLineInput", storyline.get_attribute('data-widget'))


class StorylineWidgetUnitTest(TestCase):

    def setUp(self):

        self.data = {
                "datetime_column_name": "date",
                "datetime_format": "%Y-%m-%d",
                "data_column_name": "income"}

        self.invalid_data = {
                "datetime_format": "%Y-%m-%d",
                "data_column_name": "income"
        }

        self.chart = {
                "datetime_format": "%Y",
                "y_axis_label": "Income"
            }

        self.invalid_chart = {
            "datetime_format": "%Y",
            "y_axis_label": "Income"
        }

        self.slider = {
                "start_at_card": "1",
                "title_column_name": "title",
                "text_column_name": "text",
            }

        self.invalid_slider = {
            "start_at_card": "1",
            "title_column_name": "title",
            "text_column_name": "text",
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

        self.storylineWidget = forms.Charfield(widget=UrlStoryLineInput(attrs=self.attrs))

        # def test_widget_construction(self):


