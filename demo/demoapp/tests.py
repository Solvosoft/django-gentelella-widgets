from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium.webdriver.chrome.webdriver import WebDriver

# Create your tests here.


class StoryMapWithSeleniumTestCase(StaticLiveServerTestCase):

    @classmethod
    def setUp(cls):
        super().setUp()
        cls.selenium = WebDriver(executable_path='/Users/mariovargas/Desktop/chromedriver')
        cls.live_server_url = 'http://127.0.0.1:8000/'

    @classmethod
    def tearDown(cls):
        cls.selenium.quit()
        super().tearDown()

    def test_display_gigapixel_storymap(self):
        selenium = self.selenium
        selenium.get(self.live_server_url)
        # Find storymap obj
        assert 'id_storymap' in self.selenium.page_source

