"""What the browser tests of a project built on djgentelella reuse (W24): the
settings the migrations load, back after the flush of a live server test
(``load_default_settings``), and a mouse click on an element below the fold
of a page that scrolls smoothly (``djgentelella.testing.mouse_click``)."""
from django.test import tag

from djgentelella.utils import DEFAULT_SETTINGS

from .base import SeleniumTestCase


@tag('selenium')
class ConsumerHelpersTest(SeleniumTestCase):

    default_settings = True

    def test_the_settings_are_back_after_the_flush(self):
        self.go('/')
        self.assertIn(DEFAULT_SETTINGS['site_title'], self.driver.title)
        hrefs = self.js("return Array.prototype.map.call("
                        "  document.querySelectorAll('link[rel=stylesheet]'),"
                        "  function (link) { return link.getAttribute('href'); });")
        self.assertTrue(any('gentelella/css/custom.css' in href for href in hrefs),
                        hrefs)
        self.assertFalse(any(href.startswith('/static/?') for href in hrefs), hrefs)

    def test_a_mouse_click_below_the_fold(self):
        self.go('/')
        self.js("document.documentElement.style.scrollBehavior = 'smooth';"
                "var spacer = document.createElement('div');"
                "spacer.style.height = '4000px';"
                "var button = document.createElement('button');"
                "button.id = 'w24_far'; button.type = 'button';"
                "button.textContent = 'Far away';"
                "button.addEventListener('click', function () {"
                "  window.w24_clicked = (window.w24_clicked || 0) + 1; });"
                "var main = document.querySelector('.right_col') || document.body;"
                "main.appendChild(spacer); main.appendChild(button);")
        self.mouse_click('#w24_far')
        self.wait_js('return window.w24_clicked === 1',
                     message='the click never reached the button')
        self.assert_clickable('#w24_far')
