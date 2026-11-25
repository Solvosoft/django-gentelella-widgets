"""The ``wizard`` design component in the browser (``djgentelella.wizard``):
the demo's "Hire an employee" is filled half way with a file uploaded in
chunks, saved as a draft, resumed from another session and finished."""
import json
from datetime import date
from pathlib import Path

from django.test import tag

import demoapp
from demoapp.models import NewHire
from djgentelella.designs import engine, publishing
from djgentelella.models import ChunkedUpload, WizardDraft

from .base import EC, By, SeleniumTestCase

DESIGN = Path(demoapp.__file__).parent / 'gtdesign' / 'employee_wizard.json'
PAGE = '/designs/employees/new/'
CONTRACT = b'%PDF-1.4 signed contract\n' * 50


@tag('selenium')
class WizardDraftTest(SeleniumTestCase):

    def setup_data(self):
        engine.clear_cache()
        _page, errors = publishing.publish(json.loads(DESIGN.read_text()))
        self.assertEqual(errors, [])

    def field(self, name):
        return self.driver.find_element(By.NAME, name)

    def press(self, action):
        self.mouse_click('.gt-wizard-buttons button[value="%s"]' % action)

    def position(self):
        return self.wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, '.gt-wizard-position'))).text

    def wait_position(self, text):
        self.wait.until(lambda d: text in self.position(),
                        'the wizard is not at "%s"' % text)

    def test_a_draft_saved_half_way_is_resumed_and_finished(self):
        self.go(PAGE)
        self.wait_position('1')
        self.assertEqual(self.position(), 'Paso 1 de 2: Personal data')
        self.field('personal-name').send_keys('Ana Mora')
        self.field('personal-email').send_keys('ana@example.com')
        self.press('next')
        self.wait_position('2 de 2')

        # The contract goes up in chunks; the token is what the form posts.
        path = self.write_temp_file('contract.pdf', CONTRACT)
        self.assert_widget_ready('#id_job-contract')
        self.driver.find_element(By.ID, 'id_job-contract').send_keys(path)
        self.wait.until(lambda d: self.js(
            "return document.querySelector('input.chunkedvalue').value;"),
            'the upload never finished')
        self.js("document.getElementById('id_job-start_date').value = arguments[0];",
                '01/12/2026')
        self.press('save')
        self.wait_position('2 de 2')
        self.wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, '.alert-success')))
        draft = WizardDraft.objects.get()
        self.assertEqual(draft.data['current'], 'job')
        self.assertEqual(len(draft.uploads), 1)

        # Another session of the same user: the draft is listed and resumed.
        self.driver.delete_all_cookies()
        self.login()
        self.go(PAGE)
        self.wait_position('1 de 2')
        self.assertEqual(self.field('personal-name').get_attribute('value'), '')
        self.mouse_click('.gt-wizard-resume')
        self.wait_position('2 de 2')
        self.assertIn('contract.pdf',
                      self.driver.find_element(By.CSS_SELECTOR,
                                               '.gt-wizard-uploaded').text)
        self.assertEqual(self.field('job-start_date').get_attribute('value'),
                         '01/12/2026')
        # Back and forth keeps what was typed.
        self.press('previous')
        self.wait_position('1 de 2')
        self.assertEqual(self.field('personal-name').get_attribute('value'),
                         'Ana Mora')
        self.press('next')
        self.wait_position('2 de 2')
        self.press('finish')
        self.wait.until(lambda d: NewHire.objects.exists(), 'nothing was saved')
        hire = NewHire.objects.get()
        self.assertEqual((hire.name, hire.email, hire.start_date),
                         ('Ana Mora', 'ana@example.com', date(2026, 12, 1)))
        with hire.contract.open('rb') as handle:
            self.assertEqual(handle.read(), CONTRACT)
        hire.contract.delete()
        self.assertFalse(WizardDraft.objects.exists())
        self.assertFalse(ChunkedUpload.objects.exists())
        # Finished: the page starts a new one.
        self.wait_position('1 de 2')
        self.assertFalse(self.driver.find_elements(By.CSS_SELECTOR,
                                                   '.gt-wizard-resume'))
