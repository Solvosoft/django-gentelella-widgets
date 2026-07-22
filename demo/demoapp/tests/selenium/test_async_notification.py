"""
Browser end-to-end test for the async_notification GUI.

Drives the real admin interface (login as admin/admin12345, compose an email
through the modal + TinyMCE, save) and validates reception through MailHog.
This exercises the full user-facing stack: auth/permissions, the ObjectCRUD
modal, TinyMCE, the DRF create serializer (single-email coercion), the
post-save signal, SMTP, and delivery.

Requires selenium, a chromium/chromedriver, and a running MailHog
(SMTP :1025, API :8025). Gated behind MAILHOG_E2E=1 so it never runs in the
default suite / CI. Run with:

    make mailhog          # start the receiver
    make test-browser     # MAILHOG_E2E=1 python manage.py test ...selenium
"""

import json
import os
import time
import unittest
import urllib.request

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings

MAILHOG_API = os.getenv('MAILHOG_API', 'http://localhost:8025')
CHROMEDRIVER = os.getenv('CHROMEDRIVER', '/usr/bin/chromedriver')
CHROMIUM = os.getenv('CHROME_BIN', '/usr/bin/chromium')


def _mailhog_up():
    try:
        urllib.request.urlopen(f'{MAILHOG_API}/api/v2/messages?limit=1',
                               timeout=3).read()
        return True
    except Exception:
        return False


def _requirements_met():
    if not os.getenv('MAILHOG_E2E'):
        return False, 'set MAILHOG_E2E=1 to run the browser E2E'
    try:
        import selenium  # noqa: F401
    except ImportError:
        return False, 'selenium not installed'
    if not os.path.exists(CHROMEDRIVER):
        return False, f'chromedriver not found at {CHROMEDRIVER}'
    if not _mailhog_up():
        return False, f'MailHog not reachable at {MAILHOG_API}'
    return True, ''


_OK, _REASON = _requirements_met()


@unittest.skipUnless(_OK, _REASON)
@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
    EMAIL_HOST='localhost', EMAIL_PORT='1025',
    DEFAULT_FROM_EMAIL='no-reply@example.com')
class ComposeEmailBrowserTest(StaticLiveServerTestCase):
    SUBJECT = '[SEL] Compose via browser'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        opts = Options()
        opts.add_argument('--headless=new')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--window-size=1400,1000')
        if os.path.exists(CHROMIUM):
            opts.binary_location = CHROMIUM
        cls.driver = webdriver.Chrome(
            service=Service(CHROMEDRIVER), options=opts)
        cls.driver.implicitly_wait(2)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def setUp(self):
        User = get_user_model()
        u = User.objects.create_user(
            username='admin', email='admin@example.com',
            password='admin12345')
        u.is_superuser = u.is_staff = True
        u.save()
        self._mh_reset()

    # -- MailHog helpers -----------------------------------------------------
    def _mh_reset(self):
        urllib.request.urlopen(urllib.request.Request(
            f'{MAILHOG_API}/api/v1/messages', method='DELETE'),
            timeout=10).read()

    def _mh_for(self, subject):
        data = json.loads(urllib.request.urlopen(
            f'{MAILHOG_API}/api/v2/messages?limit=1000', timeout=10).read())
        return [m for m in data['items']
                if (m['Content']['Headers'].get('Subject')
                    or [''])[0] == subject]

    # -- test ----------------------------------------------------------------
    def test_compose_and_send_email(self):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        d = self.driver
        wait = WebDriverWait(d, 25)

        # Login (protected page -> login form -> back to the page).
        d.get(f'{self.live_server_url}/async_notification/email-notifications/')
        wait.until(EC.presence_of_element_located((By.NAME, 'username')))
        d.find_element(By.NAME, 'username').send_keys('admin')
        d.find_element(By.NAME, 'password').send_keys('admin12345')
        d.find_element(
            By.CSS_SELECTOR, 'button[type=submit], input[type=submit]').click()

        wait.until(EC.presence_of_element_located((By.ID, 'datatable')))
        self.assertFalse(d.find_elements(By.NAME, 'username'),
                         'login did not succeed')
        wait.until(lambda drv: drv.execute_script(
            "return typeof tinymce!=='undefined' "
            "&& tinymce.get('id_create-message')!=null"))

        # Compose through the modal, as the user would.
        d.execute_script(
            "new bootstrap.Modal('#create_modal').show();"
            "$('[name=create-subject]').val(arguments[0]);"
            "$('[name=create-recipients]').val('browser@example.com');"
            "tinymce.get('id_create-message')"
            ".setContent('<p>Enviado desde el navegador</p>');"
            "tinymce.triggerSave();"
            "$('#id_create-enqueued').prop('checked', false)"
            ".trigger('change');",
            self.SUBJECT)
        time.sleep(0.6)
        d.find_element(By.CSS_SELECTOR, '#create_modal .formadd').click()

        # Validate reception in MailHog.
        got = []
        for _ in range(50):
            got = self._mh_for(self.SUBJECT)
            if got:
                break
            time.sleep(0.4)
        self.assertEqual(len(got), 1, 'expected exactly one email in MailHog')
        raw = got[0].get('Raw', {})
        self.assertIn('browser@example.com', raw.get('To', []))
        self.assertIn('Enviado desde el navegador', raw.get('Data', ''))
