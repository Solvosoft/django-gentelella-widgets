"""
Browser end-to-end test for the async_notification GUI.

Drives the real admin interface (login as admin/admin12345, compose an email
through the modal + TinyMCE, save) and validates reception through MailHog.
This exercises the full user-facing stack: auth/permissions, the ObjectCRUD
modal, TinyMCE, the DRF create serializer (single-email coercion), the
post-save signal, SMTP, and delivery.

Tagged ``selenium``, so the default suite (``--exclude-tag=selenium``) never
starts a browser. On top of what :class:`SeleniumTestCase` already needs
(selenium, chromium + chromedriver) this one also wants a running MailHog
(SMTP :1025, API :8025); it skips cleanly at ``setUpClass`` when MailHog is
unreachable. Run with::

    make mailhog          # start the receiver
    make test-selenium    # everything tagged selenium, inside Xvfb
"""

import json
import os
import time
import unittest
import urllib.request

from django.test import override_settings, tag

from .base import EC, By, SeleniumTestCase

MAILHOG_API = os.getenv('MAILHOG_API', 'http://localhost:8025')


def _mailhog_up():
    try:
        urllib.request.urlopen(f'{MAILHOG_API}/api/v2/messages?limit=1',
                               timeout=3).read()
        return True
    except Exception:
        return False


@tag('selenium')
@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
    EMAIL_HOST='localhost', EMAIL_PORT='1025',
    DEFAULT_FROM_EMAIL='no-reply@example.com')
class ComposeEmailBrowserTest(SeleniumTestCase):
    SUBJECT = '[SEL] Compose via browser'

    @classmethod
    def setUpClass(cls):
        # Probed before super(), which is where the browser starts: the default
        # suite must never reach MailHog and a missing receiver must not cost a
        # driver launch.
        if not _mailhog_up():
            raise unittest.SkipTest(f'MailHog not reachable at {MAILHOG_API}')
        super().setUpClass()

    def setup_data(self):
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
        d = self.driver

        self.go('/async_notification/email-notifications/')
        self.wait.until(EC.presence_of_element_located((By.ID, 'datatable')))
        self.assertFalse(d.find_elements(By.NAME, 'username'),
                         'login did not succeed')
        self.wait_js(
            "return typeof tinymce!=='undefined' "
            "&& tinymce.get('id_create-message')!=null")

        # Compose through the modal, as the user would. Without a
        # triggerSave(): a modal is read by javascript rather than submitted,
        # so flushing the editor is the form serializer's job, and doing it
        # here would hide it going missing.
        self.js(
            "new bootstrap.Modal('#create_modal').show();"
            "$('[name=create-subject]').val(arguments[0]);"
            "$('[name=create-recipients]').val('browser@example.com');"
            "tinymce.get('id_create-message')"
            ".setContent('<p>Enviado desde el navegador</p>');"
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
