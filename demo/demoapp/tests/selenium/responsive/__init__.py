from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
#from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.firefox.webdriver import WebDriver
from pathlib import Path
from django.conf import settings
import shutil
from Screenshot import Screenshot

class ScreenshotSeleniumTest(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super(ScreenshotSeleniumTest, cls).setUpClass()

        cls.timeout =10
        cls.resolutions=[{'width': 1920,'height': 1080},
                         {'width': 1366,'height': 768},
                         {'width': 1536,'height': 864},
                         {'width': 1280, 'height': 720},
                         {'width': 1440, 'height': 900},
                         {'width': 1600, 'height': 900},
                         {'width': 360, 'height': 800},
                         {'width': 414, 'height': 896},
                         {'width': 360, 'height': 640},
                         {'width': 390, 'height': 844},
                         {'width': 412, 'height': 915},
                         {'width': 360, 'height': 780},
                         {'width': 393, 'height': 873},
                         {'width': 768, 'height': 1024},
                         {'width': 1280, 'height': 800},
                         {'width': 810, 'height': 1080},
                         {'width': 800, 'height': 1280},
                         {'width': 601, 'height': 962},
                         {'width': 962, 'height': 601}]

        cls.ob = Screenshot.Screenshot()
        cls.selenium = WebDriver()
        cls.selenium.implicitly_wait(cls.timeout)

        cls.width = cls.resolutions[0]['width']
        cls.height = cls.resolutions[0]['height']
        cls.tmp = Path(settings.BASE_DIR) / 'tmp'
        cls.folder = '%s/%dx%d' % (cls.tmp, cls.width, cls.height)
        cls.dir = Path(settings.BASE_DIR) / cls.folder
        cls.server_thread.port = 8012
        if not cls.tmp.exists():
           cls.tmp.mkdir()

    def screenShots(self, name, url):
        self.selenium.get(url)

        for resolution in self.resolutions:

            self.selenium.set_window_size(resolution['width'],resolution['height'])

            print("Window size: width = {}px, height = {}px".format(resolution['width'], resolution['height']))

            x_Page = 'PAGE_SCREENSHOT_%s.png' % name
            x_Full_Page = 'Full_PAGE_SCREENSHOT_%s.png' % name
            self.folder = '%s/%dx%d' % (self.tmp, resolution['width'], resolution['height'])
            self.dir = Path(settings.BASE_DIR) / self.folder

            if not self.dir.exists():
                self.dir.mkdir()

            self.selenium.save_screenshot(str(Path(self.dir / x_Page).absolute().resolve()))
            self.selenium.save_full_page_screenshot(str(Path(self.dir / x_Full_Page).absolute().resolve()))

    def test_snaptshot(self):
        name = 'home'
        url = self.live_server_url + str(reverse(name))
        self.selenium.get(url)
        print("Headless Firefox Initialized")
        print(self.selenium.get_window_size())
        self.screenShots(name, url)
    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super(ScreenshotSeleniumTest, cls).tearDownClass()