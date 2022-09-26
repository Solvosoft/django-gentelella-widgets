from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from selenium.webdriver.chrome.webdriver import WebDriver
from pathlib import Path
from django.conf import settings
import shutil
from Screenshot import Screenshot

class ScreenshotSeleniumTest(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super(ScreenshotSeleniumTest, cls).setUpClass()


        cls.timeout = 10
        cls.ob = Screenshot.Screenshot()
        cls.selenium = WebDriver()
        cls.selenium.implicitly_wait(cls.timeout)
        cls.dir = Path(settings.BASE_DIR) / 'tmp/'
        if cls.dir.exists():
            shutil.rmtree(str(cls.dir.absolute().resolve()))

        cls.dir.mkdir()

    def test_snaptshot(self):
        url = self.live_server_url + str(reverse('home'))
        self.selenium.get(url)
        print("Headless Chrome Initialized")
        print(self.selenium.get_window_size())
        self.selenium.set_window_size(800, 600)
        size = self.selenium.get_window_size()
        print("Window size: width = {}px, height = {}px".format(size["width"], size["height"]))

       # self.selenium.find_element_by_tag_name('body').screenshot(str(Path(self.dir / 'bodypantallazo.png').absolute().resolve()))
        self.selenium.save_screenshot(str(Path(self.dir / 'pantallazo.png').absolute().resolve()))


        img_url = self.ob.full_Screenshot(self.selenium, save_path=str(self.dir), image_name='Myimage.png')
        print(img_url)
    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super(ScreenshotSeleniumTest, cls).tearDownClass()