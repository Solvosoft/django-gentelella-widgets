from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By


class StoryMapWithSeleniumTestCase(StaticLiveServerTestCase):
    """ Storymaps tests using Selenium"""

    @classmethod
    def setUpClass(cls):
        """ Set up class for Selenium tests """
        cls.selenium = WebDriver()
        cls.selenium.implicitly_wait(10)
        super(StoryMapWithSeleniumTestCase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        """ Tear Down class for Selenium tests """
        cls.selenium.quit()
        super(StoryMapWithSeleniumTestCase, cls).tearDownClass()

    def test_display_storymaps_gigapixel(self):
        """ Display both Gigapixel and MapBased storymaps """

        url = self.live_server_url + str(reverse('gigapixel_view'))
        self.selenium.get(url)
        self.assertIn('gigapixel_storymap', self.selenium.page_source)
        response = self.selenium.find_element(By.CSS_SELECTOR, 'body').text
        self.assertIn('A Sunday on La Grande Jatte', response)

    def test_display_storymaps_mapbased(self):
        """ Display both Gigapixel and MapBased storymaps """

        url = self.live_server_url + str(reverse('mapbased_view'))
        self.selenium.get(url)
        self.assertIn('mapbased_storymap', self.selenium.page_source)
        response = self.selenium.find_element(By.CSS_SELECTOR, 'body').text
        self.assertIn('COSTA RICA PLACES TO VISIT', response)
