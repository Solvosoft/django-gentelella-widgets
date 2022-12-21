from django.test import TestCase, RequestFactory
from django.urls import reverse

from djgentelella.views.storymap import BaseStoryMapMBView, BaseStoryMapGPView


class MapBasedStoryMapWidgetTestCase(TestCase):
    """ MapBased storymap widget tests """

    def setUp(self):
        """ Set up method for the tests """
        self.factory = RequestFactory()
        self.mapbased_view = BaseStoryMapMBView()
        self.url = reverse('examplestorymapmb-list')

    def test_assert_response_valid_data(self):
        """ Test response valid data from the Gtstorymap example"""
        request = self.factory.get(self.url)
        response = self.mapbased_view.list(request)

        self.assertEqual(response.status_code, 200)


class GigaPixelStoryMapWidgetTestCase(TestCase):
    """ GigaPixel storymap widget tests """

    def setUp(self):
        """ Set up method for the tests """
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
                "attribution":
                    "<a href='http://www.google.com/culturalinstitute/asset-viewer/" +
                    "a-sunday-on-la-grande-jatte-1884/twGyqq52R-lYpA?projectId=" +
                    "art-project' target='_blank'>Google Art Project</a>"
            }
        }

    def test_assert_response_valid_data(self):
        """ Test response valid data from the Gtstorymap example"""
        request = self.factory.get(self.url)
        response = self.gigapixel_view.list(request)

        self.assertEqual(response.status_code, 200)
