from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
#from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.firefox.webdriver import WebDriver
from selenium.webdriver.firefox.options import Options
from pathlib import Path
from django.conf import settings
import shutil
from Screenshot import Screenshot
import time
from selenium.webdriver.support.wait import WebDriverWait


class ScreenshotSeleniumTest(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super(ScreenshotSeleniumTest, cls).setUpClass()

        cls.timeout =10
        cls.ob = Screenshot.Screenshot()
        cls.selenium = WebDriver()
        cls.selenium.implicitly_wait(cls.timeout)
        cls.dir = Path(settings.BASE_DIR) / 'tmp/1920×1080/'
        cls.server_thread.port= 8012
        if not cls.dir.exists():
            cls.dir.mkdir()


    def test_snaptshot(self):
        name = 'home'
        url = self.live_server_url + str(reverse(name))
        self.selenium.get(url)
        print("Headless Firefox Initialized")
        print(self.selenium.get_window_size())
        self.selenium.set_window_size(1920, 1080)
        size = self.selenium.get_window_size()
        print("Window size: width = {}px, height = {}px".format(size["width"], size["height"]))
        x_Page='PAGE_SCREENSHOT_%s.png'% name
        x_Full_Page = 'Full_PAGE_SCREENSHOT_%s.png' % name

        self.selenium.save_screenshot(str(Path(self.dir / x_Page).absolute().resolve()))
        self.selenium.save_full_page_screenshot(str(Path(self.dir / x_Full_Page).absolute().resolve()))
        self.selenium.quit()
    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super(ScreenshotSeleniumTest, cls).tearDownClass()