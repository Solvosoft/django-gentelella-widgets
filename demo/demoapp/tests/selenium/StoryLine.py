from django.contrib.staticfiles.testing import StaticLiveServerTestCase
#from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.firefox.webdriver import WebDriver
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
        url = self.live_server_url + str(reverse('storyline_view'))
        self.selenium.get(url)
        self.assertIn('id_storyline', self.selenium.page_source)

    def test_widget_in_page(self):
        url = self.live_server_url + str(reverse('storyline_view'))
        self.selenium.get(url)
        storyline = self.selenium.find_element(By.CLASS_NAME, 'storyline-wrapper')
        #storyline = self.selenium.find_element_by_class_name()
        # deprecated, change to find element(by='class_name', value= "")

        self.assertNotEqual(storyline, None)
        self.assertEqual("/gtapis/storyline/", storyline.get_attribute('data-url'))
        self.assertEqual("storyline-wrapper", storyline.get_attribute('class'))
        self.assertEqual("568", storyline.get_attribute('height'))
        #self.assertEqual("1112", storyline.get_attribute('width'))
        self.assertEqual("UrlStoryLineInput", storyline.get_attribute('data-widget'))
