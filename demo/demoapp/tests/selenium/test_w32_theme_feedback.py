"""W32 in the browser: the theme roller previews and saves a colour that
every page then uses, and a feedback sent from the button is answered from
the inbox, which notifies its author."""
from django.test import tag

from djgentelella.models import Feedback, Notification, SiteTheme

from .base import By, EC, SeleniumTestCase


def css_color(driver, selector):
    return driver.execute_script(
        "var e = document.querySelector(arguments[0]);"
        "return e ? getComputedStyle(e).backgroundColor : null;", selector)


@tag('selenium')
class ThemeRollerTest(SeleniumTestCase):

    def root_primary(self):
        return self.js("return getComputedStyle(document.documentElement)"
                       ".getPropertyValue('--bs-primary').trim();")

    def test_change_the_primary_colour(self):
        self.go('/gt-theme/?site=global')
        sample = '#gt-theme-sample-primary'
        before = css_color(self.driver, sample)
        self.assertNotEqual(before, 'rgb(18, 52, 86)')
        field = self.driver.find_element(By.NAME, 'primary')
        # The colour picker sits next to the field.
        self.assertTrue(self.js("return !!document.querySelector("
                                "'input.gt-theme-picker[type=color]')"))
        field.clear()
        field.send_keys('#123456')
        # The live preview: the page itself takes the value, unsaved.
        self.wait_js("var e = document.querySelector(arguments[0]);"
                     "return getComputedStyle(e).backgroundColor === "
                     "'rgb(18, 52, 86)';", sample,
                     message='the preview never showed the new colour')
        self.assertFalse(SiteTheme.objects.exists())
        # The radius too.
        radius = self.driver.find_element(By.NAME, 'border_radius')
        radius.clear()
        radius.send_keys('8')
        self.wait_js("return getComputedStyle(document.documentElement)"
                     ".getPropertyValue('--bs-border-radius').trim() === '8px';")
        self.mouse_click('#gt-theme-save')
        self.wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, '.alert-success')))
        theme = SiteTheme.objects.get(site=None)
        self.assertEqual((theme.primary, theme.border_radius), ('#123456', 8))
        # Any other page links the saved stylesheet, with its version.
        self.go('/gt-feedback/')
        link = self.js("var l = document.querySelector('link[data-gt-theme]');"
                       "return l ? l.getAttribute('href') : null;")
        self.assertTrue(link.endswith('?v=%d' % theme.version), link)
        self.assertEqual(self.root_primary(), '#123456')
        self.assertEqual(css_color(self.driver, '.gt-feedback-button'),
                         'rgb(18, 52, 86)')


@tag('selenium')
class FeedbackTest(SeleniumTestCase):

    def test_send_and_answer(self):
        self.go('/gt-feedback/')
        self.mouse_click('.gt-feedback-button')
        self.wait.until(EC.visibility_of_element_located(
            (By.ID, 'gt-feedback-modal')))
        self.driver.find_element(By.ID, 'id_gtfeedback-text').send_keys(
            'The report button does nothing')
        self.driver.find_element(
            By.CSS_SELECTOR, '#id_gtfeedback-kind option[value=bug]').click()
        self.mouse_click('.gt-feedback-send')
        self.wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, '.gt-feedback-result.alert-success')))
        feedback = Feedback.objects.get()
        self.assertEqual((feedback.kind, feedback.user, feedback.url),
                         ('bug', self.user, '/gt-feedback/'))
        self.assertIn('x', feedback.browser)
        # The inbox lists it; its page answers it.
        self.go('/gt-feedback/')
        self.wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'tr.gt-feedback-row[data-feedback="%d"] a'
             % feedback.pk))).click()
        self.wait.until(EC.presence_of_element_located(
            (By.ID, 'id_answer-response'))).send_keys('Fixed in the next release.')
        self.mouse_click('form.gt-feedback-answer button[type=submit]')
        self.wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, '.alert-success')))
        feedback.refresh_from_db()
        self.assertEqual((feedback.status, feedback.response),
                         ('answered', 'Fixed in the next release.'))
        self.assertTrue(Notification.objects.filter(user=self.user).exists())
        self.assertEqual(self.driver.find_element(
            By.CSS_SELECTOR, '.gt-feedback-status').text,
            str(feedback.get_status_display()))
