import json

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium.webdriver.chrome.webdriver import WebDriver

from django import forms
from django.test import Client, TestCase
from django.urls import reverse, reverse_lazy

from rest_framework import status, serializers

from djgentelella.widgets.storymap import MapBasedStoryMapInput, GigaPixelStoryMapInput


class StoryMapWithSeleniumTestCase(StaticLiveServerTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.selenium = WebDriver(executable_path='/Users/mariovargas/Desktop/chromedriver')
        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def test_display_gigapixel_storymap(self):
        selenium = self.selenium
        selenium.get(self.live_server_url)
        # Find storymap obj
        assert 'mapbased_storymap' in self.selenium.page_source
        assert 'gigapixel_storymap' in self.selenium.page_source


class MapBasedStoryMapWidgetTestCase(TestCase):

    def setUp(self):
        self.client = Client()
        self.storymap = forms.CharField(widget=MapBasedStoryMapInput(
            attrs={"data-url": reverse_lazy('examplestorymapmb-list')}))

        self.url = reverse('examplestorymapmb-list')

    def test_mapbased_storymap_api_ok(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_assert_response_data(self):
        response = self.client.get(self.url)
        self.assertEqual(json.loads(response.content)['storymap']['slides'][0]['type'], 'overview')
        self.assertEqual(json.loads(response.content)['storymap']['slides'][1]['text']['headline'], 'MONTEVERDE')
        self.assertEqual(json.loads(response.content)['storymap']['slides'][2]['location']['name'],
                         'MANUEL ANTONIO NATIONAL PARK')
        self.assertEqual(json.loads(response.content)['storymap']['slides'][3]['media']['credit'], 'wikipedia')
        self.assertEqual(json.loads(response.content)['storymap']['slides'][4]['location']['zoom'], 10)
        self.assertEqual(json.loads(response.content)['storymap']['slides'][5]['date'], '')


class GigaPixelStoryMapWidgetTestCase(TestCase):

    def setUp(self):
        self.client = Client()
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

    def get_storymap_body(self):
        return {
            "font_css": 'stock:opensans-gentiumbook',
            "storymap": {
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
        }

    def test_gigapixel_storymap_api_ok(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_assert_response_data(self):
        response = self.client.get(self.url)
        self.assertEqual(json.loads(response.content)['storymap']['map_type'], 'zoomify')
        self.assertEqual(json.loads(response.content)['font_css'], 'stock:opensans-gentiumbook')

        self.assertEqual(json.loads(response.content)['storymap']['slides'][0]['location']['line'], True)
        self.assertEqual(json.loads(response.content)['storymap']['slides'][1]['text']['headline'],
                         'Small Horizontal Brushstrokes')
        self.assertEqual(json.loads(response.content)['storymap']['slides'][2]['date'], '')
        self.assertEqual(json.loads(response.content)['storymap']['slides'][3]['text']['text'],
                         'He later added small dots, also in complementary colors.')

    '''
    def test_bad_request_data(self):
        data = self.get_storymap_body()
        data['storymap']['slides'][0]['location'] = 'foo'

        storymap = forms.CharField(widget=GigaPixelStoryMapInput(attrs={"data-url": '',
                                                                        "storymap_options": self.get_storymap_options()}))'''

