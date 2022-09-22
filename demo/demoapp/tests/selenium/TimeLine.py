from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium.webdriver.chrome.webdriver import WebDriver
from django.urls import reverse
from selenium.webdriver.common.by import By

class StorylineWidgetSeleniumTest(StaticLiveServerTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.selenium = WebDriver()
        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super(StorylineWidgetSeleniumTest, cls).tearDownClass()

    def test_widget_assignation(self):
        url = self.live_server_url + str(reverse('timeline_view'))
        self.selenium.get(url)
        self.assertIn('id_timeline', self.selenium.page_source)

    def test_widget_in_page(self):
        url = self.live_server_url + str(reverse('timeline_view'))
        self.selenium.get(url)
        timeline = self.selenium.find_element(By.CLASS_NAME, 'tl-timeline')
        #storyline = self.selenium.find_element_by_class_name()
        # deprecated, change to find element(by='class_name', value= "")

        self.assertNotEqual(timeline, None)
        self.assertEqual("/gtapis/timeline/", timeline.get_attribute('data-url'))
        self.assertEqual("UrlTimeLineInput", timeline.get_attribute('data-widget'))
